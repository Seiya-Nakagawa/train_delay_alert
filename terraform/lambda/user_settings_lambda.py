# -*- coding: utf-8 -*-
"""ユーザー設定を管理するLambdaハンドラ (データモデル変更版).

DynamoDBのデータモデルを「ユーザーの各設定・各路線ごとに1つのアイテム」
という構造に変更したことに伴い、データ取得・保存ロジックを全面的に刷新しています。

- データ取得: Query操作でユーザーに関連する全アイテムを取得し、フロントエンド向けのJSONに再構築します。
- データ保存: BatchWriteItem操作で、ユーザーの古い設定をすべて削除し、新しい設定を一括で書き込みます。
"""

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
PROFILE_KEY = "#PROFILE#"  # ユーザー設定情報を格納するアイテムのソートキー

ssm_client = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USER_TABLE_NAME)


# --- ヘルパー関数 ---


def get_ssm_parameter(ssm_param_name):
    """SSMパラメータストアから指定されたパラメータの値を取得します。"""
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print(f"Error getting parameter {ssm_param_name}: {e}")
        raise


# 起動時にLINEチャネルシークレットを取得
LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_CHANNEL_SECRET_PARAM_NAME)


def get_line_user_id(body):
    """LINEの認可コードを使用して、LINEユーザーIDを取得します。"""
    auth_code = body.get("authorizationCode")
    if not auth_code:
        raise ValueError("認可コードが必要です。")

    response = requests.post(
        LINE_TOKEN_URL,
        headers={"Content-Type": "application/x-w-form-urlencoded"},
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
        print(f"ERROR: IDトークンの抽出に失敗しました。Response: {response_json}")
        raise ValueError("IDトークンの抽出に失敗しました。")

    verify_response = requests.post(
        LINE_VERIFY_URL, data={"id_token": id_token, "client_id": LINE_CHANNEL_ID}
    )
    verify_response.raise_for_status()

    verify_json = verify_response.json()
    line_user_id = verify_json.get("sub")
    if not line_user_id:
        print(f"ERROR: LINEユーザIDの取得に失敗しました。Response: {verify_json}")
        raise ValueError("LINEユーザIDの取得に失敗しました。")

    return line_user_id


# --- データ操作関数 (新しいデータモデルに対応) ---


def get_user_data(line_user_id):
    """DynamoDBからユーザーの全データを取得し、フロントエンド向けの形式に再構築します。"""
    try:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("lineUserId").eq(
                line_user_id
            )
        )
        items = response.get("Items", [])
        if not items:
            return None

        # プロフィール情報と路線情報を分離
        user_profile = {}
        routes = []
        for item in items:
            if item["settingOrRoute"] == PROFILE_KEY:
                user_profile = item
            else:
                routes.append(item["settingOrRoute"])

        # フロントエンドが期待する単一のJSONオブジェクトに再構築
        user_data = {
            "lineUserId": user_profile.get("lineUserId"),
            "routes": sorted(routes),  # 順序を安定させるためにソート
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


def post_user_data(user_data):
    """ユーザーデータをDynamoDBに保存します。古いデータを削除し、新しいデータを一括登録します。"""
    line_user_id = user_data["lineUserId"]

    try:
        # 1. まず、このユーザーの既存のデータをすべて取得して削除対象リストを作成
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("lineUserId").eq(
                line_user_id
            ),
            ProjectionExpression="lineUserId, settingOrRoute",  # キーのみ取得で効率化
        )
        items_to_delete = response.get("Items", [])

        # 2. 新しく保存するアイテムのリストを作成
        profile_item = {
            "lineUserId": line_user_id,
            "settingOrRoute": PROFILE_KEY,
            "isAllDay": user_data.get("isAllDay"),
            "notificationStartTime": user_data.get("notificationStartTime"),
            "notificationEndTime": user_data.get("notificationEndTime"),
            "notificationDays": user_data.get("notificationDays"),
        }
        route_items = [
            {"lineUserId": line_user_id, "settingOrRoute": route}
            for route in user_data.get("routes", [])
        ]
        items_to_put = [profile_item] + route_items

        # 3. BatchWriterを使って、削除と登録を一括処理
        with table.batch_writer() as batch:
            # 古いアイテムを削除
            if items_to_delete:
                for item in items_to_delete:
                    batch.delete_item(Key=item)
            # 新しいアイテムを登録
            for item in items_to_put:
                batch.put_item(Item=item)

    except ClientError as e:
        print(f"DynamoDBへのユーザーデータ登録でエラーが発生しました: {e}")
        raise


# --- メインハンドラ ---


def lambda_handler(event, context):
    """Lambda関数のメインエントリポイント。"""
    try:
        body = json.loads(event.get("body", "{}"))
        print(f"Received event: {json.dumps(body)}")

        # 1. LINEログイン後の初回アクセス（認可コードが含まれる）
        if "authorizationCode" in body:
            line_user_id = get_line_user_id(body)
            print(f"LINEユーザーIDの取得に成功しました: {line_user_id}")

            user_data = get_user_data(line_user_id)

            # 新規ユーザーの場合、デフォルトのデータ構造を作成
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

        # 2. ユーザーによる設定情報の保存・更新（ユーザーIDが含まれる）
        elif "lineUserId" in body:
            post_user_data(body)
            print(f"ユーザー情報を更新しました: {body.get('lineUserId')}")
            return {
                "statusCode": 200,
                "body": json.dumps(body, ensure_ascii=False, default=str),
            }

        # 3. 上記以外の不正なリクエスト
        else:
            error_message = "不正なリクエストです。'authorizationCode'または'lineUserId'が含まれていません。"
            print(f"ERROR: {error_message}")
            return {"statusCode": 400, "body": json.dumps({"message": error_message})}

    # 予期せぬエラー処理
    except Exception as e:
        print(f"ERROR: 予期せぬエラーが発生しました: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": f"サーバー内部でエラーが発生しました: {str(e)}"}
            ),
        }
