import json
import os
import base64
import boto3
from linebot.v3 import LineBotApi, WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.models import MessageEvent, TextMessage, TextSendMessage

# 変数設定
CHANNEL_ACCESS_TOKEN_PARAM_NAME = os.environ.get('CHANNEL_ACCESS_TOKEN_PARAM_NAME')
CHANNEL_SECRET_PARAM_NAME = os.environ.get('CHANNEL_SECRET_PARAM_NAME')
ssm_client = boto3.client('ssm')

# --- パラメータストアから値を取得 ---
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

# --- パラメータストアから値を取得 ---
def signature_validation_check(body, signature):
    try:
        handler.handle(body, signature)

        return None
    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': json.dumps("Invalid signature. Please check your channel secret.")
        }


def lambda_handler(event, context):
    print(event)
    body       = event['body']
    signature  = event['headers']['x-line-signature']
    event_type = body['events']['type']
    user_Id = body['events']['source']['userId']

    # base64エンコードされている場合、デコード
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')

    # 署名検証
    validation_result = signature_validation_check(body, signature)
    if validation_result:
        return validation_result
    
    # イベントタイプに応じた処理
    # 友達追加
    # if event_type == 'follow':

    return {
        'statusCode': 200,
        'body': json.dumps("Hello from Lambda!")
    }