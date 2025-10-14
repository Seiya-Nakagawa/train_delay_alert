import json
import os
import base64
import boto3
from linebot import LineBotApi, WebhookHandler  # <- 修正
from linebot.exceptions import InvalidSignatureError  # <- 修正
from linebot.models import MessageEvent, TextMessage, TextSendMessage  # <- 修正```

# --- パラメータストアから値を取得 ---
# SSMクライアントを初期化
# Lambdaが実行されるリージョンを自動で取得します
region_name = os.environ.get('AWS_REGION')
ssm = boto3.client('ssm', region_name=region_name)

def get_ssm_parameter(parameter_name):
    """パラメータストアから値を取得するヘルパー関数"""
    try:
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting parameter {parameter_name}: {e}")
        raise e

# ハンドラ関数の外でパラメータを取得（コールドスタート時のみ実行）
CHANNEL_ACCESS_TOKEN = get_ssm_parameter('/train-prd/line/channel_access_token')
CHANNEL_SECRET = get_ssm_parameter('/train-prd/line/channel_secret')
# -----------------------------------

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def lambda_handler(event, context):
    signature = event['headers']['x-line-signature']
    body = event['body']

    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return {
            'statusCode': 400,
            'body': json.dumps("Invalid signature. Please check your channel secret.")
        }

    return {
        'statusCode': 200,
        'body': json.dumps("OK")
    }

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=event.message.text)
    )
    