# -*- coding: utf-8 -*-
import json
import os

import boto3
import requests
from botocore.exceptions import ClientError

# --- グローバル変数・初期設定 ---
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get("LINE_CHANNEL_SECRET_PARAM_NAME")
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL")

LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
PROFILE_KEY = "#PROFILE#"

ssm_client = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USER_TABLE_NAME)

# --- ヘルパー関数 ---


def get_ssm_parameter(ssm_param_name):
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print(f"Error getting parameter {ssm_param_name}: {e}")
        raise


LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_CHANNEL_SECRET_PARAM_NAME)


def get_line_user_id(body):
    auth_code = body.get("authorizationCode")
    if not auth_code:
        raise ValueError("認可コードが必要です。")
    response = requests.post(
        LINE_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": FRONTEND_REDIRECT_URL,
            "client_id": LINE_CHANNEL_ID,
            "client_secret": LINE_CHANNEL_SECRET,
        },
    )
    response.raise_for_status()
    response_json = response.json()
    id_token = response_json.get("id_token")
    if not id_token:
        raise ValueError("IDトークンの抽出に失敗しました。")
    verify_response = requests.post(
        LINE_VERIFY_URL, data={"id_token": id_token, "client_id": LINE_CHANNEL_ID}
    )
    verify_response.raise_for_status()
    verify_json = verify_response.json()
    line_user_id = verify_json.get("sub")
    if not line_user_id:
        raise ValueError("LINEユーザIDの取得に失敗しました。")
    return line_user_id


def get_user_data(line_user_id):
    try:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("lineUserId").eq(
                line_user_id
            )
        )
        items = response.get("Items", [])
        if not items:
            return None
        user_profile = {}
        routes = []
        for item in items:
            if item["settingOrRoute"] == PROFILE_KEY:
                user_profile = item
            else:
                routes.append(item["settingOrRoute"])
        user_data = {
            "lineUserId": user_profile.get("lineUserId"),
            "routes": sorted(routes),
            "isAllDay": user_profile.get("isAllDay", False),
            "notificationStartTime": user_profile.get("notificationStartTime", "07:00"),
            "notificationEndTime": user_profile.get("notificationEndTime", "09:00"),
            "notificationDays": user_profile.get(
                "notificationDays", ["mon", "tue", "wed", "thu", "fri"]
            ),
        }
        return user_data
    except ClientError as e:
        print(f"DynamoDBからのユーザーデータ取得でエラーが発生しました: {e}")
        raise


# --- 【重要】データ保存ロジックを差分更新方式に修正 ---
def post_user_data(user_data):
    """ユーザーデータをDynamoDBに保存します（差分更新方式）。"""
    line_user_id = user_data["lineUserId"]
    try:
        # 1. 既存の路線データを取得
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("lineUserId").eq(
                line_user_id
            )
        )
        existing_items = response.get("Items", [])
        old_routes = {
            item["settingOrRoute"]
            for item in existing_items
            if item["settingOrRoute"] != PROFILE_KEY
        }

        # 2. 新しい路線データと差分を計算
        new_routes = set(user_data.get("routes", []))
        routes_to_add = new_routes - old_routes
        routes_to_delete = old_routes - new_routes

        # 3. BatchWriterを使って、差分のみを更新
        with table.batch_writer() as batch:
            # 3a. プロフィール情報は常に上書き更新
            profile_item = {
                "lineUserId": line_user_id,
                "settingOrRoute": PROFILE_KEY,
                "isAllDay": user_data.get("isAllDay"),
                "notificationStartTime": user_data.get("notificationStartTime"),
                "notificationEndTime": user_data.get("notificationEndTime"),
                "notificationDays": user_data.get("notificationDays"),
            }
            batch.put_item(Item=profile_item)

            # 3b. 追加された路線を登録
            for route in routes_to_add:
                batch.put_item(
                    Item={"lineUserId": line_user_id, "settingOrRoute": route}
                )

            # 3c. 削除された路線を削除
            for route in routes_to_delete:
                batch.delete_item(
                    Key={"lineUserId": line_user_id, "settingOrRoute": route}
                )

    except ClientError as e:
        print(f"DynamoDBへのユーザーデータ登録でエラーが発生しました: {e}")
        raise


# --- メインハンドラ (変更なし) ---
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        print(f"Received event: {json.dumps(body)}")
        if "authorizationCode" in body:
            line_user_id = get_line_user_id(body)
            print(f"LINEユーザーIDの取得に成功しました: {line_user_id}")
            user_data = get_user_data(line_user_id)
            if not user_data:
                print(
                    f"新規ユーザーです。デフォルトデータを作成します。lineUserId: {line_user_id}"
                )
                user_data = {
                    "lineUserId": line_user_id,
                    "routes": [],
                    "isAllDay": False,
                    "notificationStartTime": "07:00",
                    "notificationEndTime": "09:00",
                    "notificationDays": ["mon", "tue", "wed", "thu", "fri"],
                }
            print("ユーザーデータの取得/作成に成功しました。レスポンスを返します。")
            return {
                "statusCode": 200,
                "body": json.dumps(user_data, ensure_ascii=False, default=str),
            }
        elif "lineUserId" in body:
            post_user_data(body)
            print(f"ユーザー情報を更新しました: {body.get('lineUserId')}")
            return {
                "statusCode": 200,
                "body": json.dumps(body, ensure_ascii=False, default=str),
            }
        else:
            error_message = "不正なリクエストです。'authorizationCode'または'lineUserId'が含まれていません。"
            print(f"ERROR: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"message": error_message})}
    except Exception as e:
        print(f"ERROR: 予期せぬエラーが発生しました: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": f"サーバー内部でエラーが発生しました: {str(e)}"}
            ),
        }
