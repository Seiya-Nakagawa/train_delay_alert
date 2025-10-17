import json
import os
import base64
import boto3
# v3から旧バージョンへの変更点 (1)
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import FollowEvent, MessageEvent, TextMessage
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

# --- グローバル変数 (変更なし) ---
CHANNEL_ACCESS_TOKEN_PARAM_NAME = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_NAME')
CHANNEL_SECRET_PARAM_NAME = os.environ.get('LINE_CHANNEL_SECRET_NAME')
TIMEZONE = timezone(timedelta(hours=+9), 'JST')
ssm_client = boto3.client('ssm')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Users')

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


# --- ユーザ情報（友達追加） (バグ修正) ---
def register_user(line_user_id):
    """DynamoDBにユーザ情報を登録する"""
    try:
        dt_now_iso = datetime.now(TIMEZONE).isoformat()

        # DynamoDBに書き込むアイテムを定義
        item = {
            'lineUserId': line_user_id,
            'userStatus': "onboarding",
            'createdAt': dt_now_iso,
            'updatedAt': dt_now_iso,
        }

        # 条件付きでアイテムを追加（既存ユーザはスキップ）
        # v3からの変更点 (4): 引数名を 'item' から 'Item' に修正
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(lineUserId)'
        )

        print(f"Successfully registered new user: {line_user_id}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"User {line_user_id} is already registered. Skipping.")
        else:
            # 予期せぬDBエラーは呼び出し元に伝える
            raise e

# --- v3からの変更点 (2): イベントハンドラの定義 ---
@handler.add(FollowEvent)
def handle_follow(event):
    """友達追加イベントを処理する"""
    line_user_id = event.source.user_id
    register_user(line_user_id)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """メッセージイベントを処理する（現在は何もしない）"""
    # メッセージイベントの処理は後で実装予定
    pass


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