import json
import os
import base64
import boto3
import requests

# v3から旧バージョンへの変更点 (1)
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent, MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, PostbackEvent, PostbackAction
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# --- グローバル変数 (変更なし) ---
LINE_CHANNEL_ID = os.environ.get('LINE_CHANNEL_ID')
LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME')
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get('LINE_CHANNEL_SECRET_PARAM_NAME')
TIMEZONE = timezone(timedelta(hours=+9), 'JST')
TABLE_NAME = os.environ.get('TABLE_NAME')
FRONTEND_REDIRECT_URL = os.environ.get('FRONTEND_REDIRECT_URL')
FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN')
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"

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

LINE_CHANNEL_ACCESS_TOKEN_NAME = get_ssm_parameter(LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME)
LINE_CHANNEL_SECRET_NAME = get_ssm_parameter(LINE_CHANNEL_SECRET_PARAM_NAME)

linebot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN_NAME)
handler = WebhookHandler(LINE_CHANNEL_SECRET_NAME)

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

def get_line_user_id(body):
    # 認可コードを取得
    auth_code = body.get('authorizationCode')
    if not auth_code:
        print("ERROR: 認可コードを取得できませんでした。")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': '認可コードが必要です。'})
        }

    # LINEのアクセストークン取得API呼び出し
    response = requests.post(
        LINE_TOKEN_URL,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': FRONTEND_REDIRECT_URL,
            'client_id': LINE_CHANNEL_ID,
            'client_secret': LINE_CHANNEL_SECRET_NAME
        }
    )

    # IDトークンの抽出
    id_token = response.json().get('id_token')

    if not id_token:
        print("ERROR: IDトークンの抽出に失敗しました。")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'IDトークンの抽出に失敗しました。'})
        }

    # LINEのプロフィール取得API呼び出し
    verify_response  = requests.post(
        LINE_VERIFY_URL,
        data={
            'id_token': id_token,
            'client_id': LINE_CHANNEL_ID
        }
    )

    # LINEユーザIDの抽出
    line_user_id = verify_response.json().get('sub')

    if not line_user_id:
        print("ERROR: LINEユーザIDの取得に失敗しました。")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'LINEユーザIDの取得に失敗しました。'})
        }
    
    return line_user_id

def get_user_data(line_user_id):
    try:
        response_userdata = table.get_item(
            Key={
                'lineUserId': line_user_id
            }
        )

        return response_userdata.get('Item')
    except Exception as e:
        print(f"Error getting user data for {line_user_id}: {e}")
        raise e

def post_user_data(body,line_user_id):
    try:
        response_userdata = table.put_item(
            Item=body
        )

        return response_userdata.get('Item')
    except Exception as e:
        print(f"Error postting user data for {line_user_id}: {e}")
        raise e

# --- v3からの変更点 (3): lambda_handlerをSDKの標準的な形式に修正 ---
def lambda_handler(event, context):
    body = json.loads(event.get('body', '{}'))

    print(f"Received event: {json.dumps(body)}")

    # LINE Login後のアクセスか判定（ログイン後は認可コードがPOSTされる）
    if 'authorizationCode' in body:
        try:
            # LINEユーザIDの取得関数呼び出し
            line_user_id = get_line_user_id(body)

            # DynamoDBのユーザ情報取得関数呼び出し
            user_data = get_user_data(line_user_id)

            if not user_data:
                # --- ユーザーが見つからなかった場合 ---
                # user_data (Itemの中身全体) をレスポンスに含める
                print(f"新規ユーザーです。lineUserId: {line_user_id}")
                user_data = {
                    'lineUserId': line_user_id,
                    'createdAt': '',
                    'updatedAt': '',
                    'routes': [],
                    'notificationSettings': {
                        'startTime': '',
                        'endTime': ''
                    }
                }
            else:
                print(f"既存ユーザーが見つかりました: {user_data}")

            return {
                'statusCode': 200,
                'body': json.dumps(user_data, ensure_ascii=False, default=str)
            }

        except Exception as e:
            print(f"ERROR: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'ユーザー情報取得処理でエラーが発生しました。'})
            }

    # データ保存リクエストの判定
    elif 'lineUserId' in body:
        try:
            line_user_id = body.get('lineUserId')

            # DynamoDBのデータ更新関数呼び出し
            post_user_data(body,line_user_id)

            print(f"ユーザー情報を更新しました: {line_user_id}")

            return {
                'statusCode': 200,
                'body': json.dumps(user_data, ensure_ascii=False, default=str)
            }

        except Exception as e:
            print(f"ERROR: ユーザー情報更新処理でエラーが発生しました: {e}")


    # どちらのパターンにも一致しない不正なリクエスト
    else:
        error_message = "不正なリクエストです。'authorizationCode'または'userId'が含まれていません。"
        print(f"ERROR: {error_message}")
        
        # ステータスコードを400（Bad Request）に変更するのがより適切
        return {
            'statusCode': 400,
            'body': json.dumps({'message': error_message})
        }