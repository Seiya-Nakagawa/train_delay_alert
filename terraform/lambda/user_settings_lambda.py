import json
import os
import base64
import boto3
# v3から旧バージョンへの変更点 (1)
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent, MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, PostbackEvent, PostbackAction
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# --- グローバル変数 (変更なし) ---
CHANNEL_ACCESS_TOKEN_PARAM_NAME = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_NAME')
CHANNEL_SECRET_PARAM_NAME = os.environ.get('LINE_CHANNEL_SECRET_NAME')
TIMEZONE = timezone(timedelta(hours=+9), 'JST')
TABLE_NAME = os.environ.get('TABLE_NAME')

ssm_client = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

# --- パラメータストアから値を取得 (変更なし) ---
def get_ssm_parameter(ssm_param_name):
    """パラメータストアから値を取得するヘルパー関数"""
    try:
        response = ssm_client.get_parameter(
            Name=ssm_param_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting parameter {ssm_param_name}: {e}")
        raise e

CHANNEL_ACCESS_TOKEN = get_ssm_parameter(CHANNEL_ACCESS_TOKEN_PARAM_NAME)
CHANNEL_SECRET = get_ssm_parameter(CHANNEL_SECRET_PARAM_NAME)

linebot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- v3からの変更点 (2): イベントハンドラの定義 ---
# @handler.add(FollowEvent)
# def handle_follow(event):
#     """友達追加イベントを処理する"""
#     register_user(event)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """メッセージイベントを処理する"""
    user_input = event.message.text
    reply_token = event.reply_token

    if user_input == "路線設定":
        send_route_selection(reply_token)
    else:
        # 「路線設定」以外のメッセージが来た場合のデフォルトの応答
        # 例: オウム返し
        linebot_api.reply_message(reply_token, TextMessage(text=f"路線設定する場合は「路線設定」と入力してください。"))

# --- DynamoDBにユーザ情報登録 ---
# def register_user(event):
#     """DynamoDBにユーザ情報を登録する"""
#     try:
#         line_user_id = event.source.user_id
#         dt_now_iso = datetime.now(TIMEZONE).isoformat()

#         # DynamoDBに書き込むアイテムを定義
#         item = {
#             'lineUserId': line_user_id,
#             'userStatus': "onboarding",
#             'createdAt': dt_now_iso,
#             'updatedAt': dt_now_iso,
#         }

#         # 条件付きでアイテムを追加（既存ユーザはスキップ）
#         # v3からの変更点 (4): 引数名を 'item' から 'Item' に修正
#         table.put_item(
#             Item=item,
#             ConditionExpression='attribute_not_exists(lineUserId)'
#         )

#         print(f"Successfully registered new user: {line_user_id}")
#     except Exception as e:
#         print(f"ユーザ登録処理に失敗しました。: {e}")
#         raise e

# --- DynamoDBのユーザ情報更新 ---
def activate_user(event):
    """DynamoDBにユーザ情報を登録する"""
    try:
        line_user_id = event.source.user_id
        user_input = event.message.text
        dt_now_iso = datetime.now(TIMEZONE).isoformat()
        reply_token = event.reply_token

        #
        if user_input == "路線設定":
            send_route_selection(reply_token)
            return

        print(f"Successfully registered new user: {line_user_id}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"User {line_user_id} is already registered. Skipping.")
        else:
            # 予期せぬDBエラーは呼び出し元に伝える
            raise e

# --- 路線リスト ---
def send_route_selection(reply_token):
    """ユーザーに路線の選択肢をクイックリプライで送信する"""
    try:
        # TODO:後からAPI取得に変更
        SUPPORTED_ROUTES = ['山手線', '京浜東北線', '中央線', '総武線', '埼京線']

        # クイックリプライの路線リストボタンを作成
        items = [
            QuickReplyButton(action=MessageAction(label=route, text=route))
            for route in SUPPORTED_ROUTES
        ]

        # 送信するメッセージオブジェクトを作成する
        # text にはユーザーへの案内文を、quick_reply には作成したボタンリストを渡す
        message = TextSendMessage(
            text="通知を受け取りたい路線を選択してください👇",
            quick_reply=QuickReply(items=items)
        )

        # print(f"TextMessage object created. Text: '{message.text}', QuickReply items: {len(message.quick_reply.items) if message.quick_reply else 'None'}")

        # 作成したメッセージを、指定された reply_token を使って返信する
        linebot_api.reply_message(reply_token, message)

        print(f"linebot_api.reply_message called successfully for reply_token: {reply_token}")

        return
    except Exception as e:
        print(f"路線リスト作成処理でエラーが発生しました: {e}")
        raise e



# --- v3からの変更点 (3): lambda_handlerをSDKの標準的な形式に修正 ---
def lambda_handler(event, context):
    """Lambdaのエントリポイント"""
    # リクエストヘッダーから署名を取得
    signature = event['headers']['x-line-signature']

    # リクエストボディを取得
    body = event['body']

    # base64エンコードされている場合、デコード
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')

    # 署名を検証し、イベントをそれぞれのハンドラにディスパッチ
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': json.dumps("Invalid signature. Please check your channel secret.")
        }

    # 成功レスポンス
    return {
        'statusCode': 200,
        'body': json.dumps("OK")
    }