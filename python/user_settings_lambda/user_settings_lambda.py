# -*- coding: utf-8 -*-
"""
ユーザー設定の取得・更新を行うLambdaハンドラ。

フロントエンドからのリクエストを受け、LINEログイン認証、
ユーザー情報の取得、および登録路線の更新処理を行う。
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# --- ログ設定 ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# --- グローバル変数・初期設定 ---
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get("LINE_CHANNEL_SECRET_PARAM_NAME")
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL")
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
USER_LIST_FILE_KEY = "user-list.json"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
RESPONSE_TIMEOUT = int(os.environ.get("RESPONSE_TIMEOUT", 10))

LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
PROFILE_KEY = "#PROFILE#"

ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
sns_client = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USER_TABLE_NAME)

try:
    # SSMパラメータストアからLINEチャネルシークレットを取得
    response = ssm_client.get_parameter(
        Name=LINE_CHANNEL_SECRET_PARAM_NAME, WithDecryption=True
    )
    LINE_CHANNEL_SECRET = response["Parameter"]["Value"]
except ClientError:
    logger.critical(
        f"パラメータ {LINE_CHANNEL_SECRET_PARAM_NAME} の取得に失敗しました。",
        exc_info=True,
    )
    raise RuntimeError(
        "Lambdaの初期化に失敗しました: LINEチャネルシークレットが取得できません。"
    )


def get_line_user_id(body: Dict[str, Any]) -> str:
    """リクエストボディから認可コードを抽出し、LINE APIを介してユーザーIDを取得する。"""
    auth_code = body.get("authorizationCode")
    if not auth_code:
        raise ValueError("認可コードが必要です。")

    # LINEトークンAPIを呼び出し、IDトークンを取得
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
        timeout=10,  # タイムアウト設定
    )

    if not response.ok:
        logger.error(
            "LINEトークンAPIからの応答でエラーが発生しました。",
            extra={
                "status_code": response.status_code,
                "response_body": response.text,
            },
        )
    response.raise_for_status()
    response_json = response.json()
    id_token = response_json.get("id_token")
    if not id_token:
        raise ValueError("IDトークンの抽出に失敗しました。")

    # LINE検証APIを呼び出し、IDトークンを検証してユーザーIDを取得
    verify_response = requests.post(
        LINE_VERIFY_URL,
        data={"id_token": id_token, "client_id": LINE_CHANNEL_ID},
        timeout=10,  # タイムアウト設定
    )
    if not verify_response.ok:
        logger.error(
            "LINE検証APIからの応答でエラーが発生しました。",
            extra={
                "status_code": verify_response.status_code,
                "response_body": verify_response.text,
            },
        )
    verify_response.raise_for_status()
    verify_json = verify_response.json()
    line_user_id = verify_json.get("sub")
    if not line_user_id:
        raise ValueError("LINEユーザーIDの取得に失敗しました。")
    return line_user_id


def get_user_data(line_user_id: str) -> Optional[Dict[str, Any]]:
    """DynamoDBからユーザーのプロフィールと登録路線を取得し、整形して返す。"""
    try:
        # railway_list.jsonを読み込んで、IDと路線のマッピングを作成
        # NOTE: 毎回ファイルを読み込むが、キャッシュを考慮する場合、グローバルスコープでの読み込みを検討。
        with open("railway_list.json", "r", encoding="utf-8") as f:
            railway_list = json.load(f)
        railway_map = {item["odpt:railway"]: item["route"] for item in railway_list}

        response = table.query(
            KeyConditionExpression=Key("lineUserId").eq(line_user_id)
        )
        items = response.get("Items", [])
        if not items:
            return None

        user_profile = {}
        route_ids = []
        for item in items:
            if item["settingOrRoute"] == PROFILE_KEY:
                user_profile = item
            else:
                route_ids.append(item["settingOrRoute"])

        # 路線IDを路線名に変換。見つからない場合はIDをそのまま使用。
        routes = [railway_map.get(route_id, route_id) for route_id in route_ids]

        user_data = {
            "lineUserId": user_profile.get("lineUserId"),
            "routes": sorted(routes),
        }
        return user_data
    except (ClientError, FileNotFoundError) as e:
        logger.error(
            f"ユーザーデータの取得でエラーが発生しました: {e}",
            exc_info=True,
        )
        raise


def get_s3_object_as_list(bucket_name: str, key: str) -> List[str]:
    """S3から指定されたJSONオブジェクトを読み込み、リストとして返す。"""
    try:
        response_s3file = s3_client.get_object(Bucket=bucket_name, Key=key)
        content_string = response_s3file["Body"].read().decode("utf-8")

        if not content_string.strip():
            logger.warning(f"S3ファイル'{key}'は空です。空のリストを返します。")
            return []

        s3_object_list = json.loads(content_string)

        if not isinstance(s3_object_list, list):
            logger.warning(
                f"S3ファイル'{key}'はJSONリスト形式ではありません。空のリストを返します。"
            )
            return []

        return s3_object_list
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info(
                f"S3オブジェクト'{key}'が見つかりませんでした。空のリストを返します。"
            )
            return []
        logger.error(
            f"S3オブジェクト'{key}'の取得中に予期せぬエラーが発生しました: {e}",
            exc_info=True,
        )
        raise
    except json.JSONDecodeError:
        logger.warning(f"S3ファイル'{key}'は不正なJSON形式です。空のリストを返します。")
        return []


def post_user_data(user_data: Dict[str, Any]):
    """ユーザーデータをDynamoDBに差分更新で保存する。"""
    line_user_id = user_data["lineUserId"]
    try:
        # 1. 既存の路線データを取得
        response = table.query(
            KeyConditionExpression=Key("lineUserId").eq(line_user_id)
        )
        existing_items = response.get("Items", [])
        old_routes = {
            item["settingOrRoute"]
            for item in existing_items
            if item["settingOrRoute"] != PROFILE_KEY
        }

        # 2. 新しい路線データと差分を計算
        new_routes = set(
            user_data.get("routes", [])
        )  # フロントエンドからは路線IDのリストが来ることを想定
        routes_to_add = new_routes - old_routes
        routes_to_delete = old_routes - new_routes

        # 3. BatchWriterを使って、差分のみを更新
        with table.batch_writer() as batch:
            # プロフィール情報は常に上書き更新
            profile_item = {"lineUserId": line_user_id, "settingOrRoute": PROFILE_KEY}
            batch.put_item(Item=profile_item)

            # 追加された路線を登録
            for route in routes_to_add:
                batch.put_item(
                    Item={"lineUserId": line_user_id, "settingOrRoute": route}
                )

            # 削除された路線を削除
            for route in routes_to_delete:
                batch.delete_item(
                    Key={"lineUserId": line_user_id, "settingOrRoute": route}
                )

        # 路線情報に変更があった場合のみS3に通知 (user-list.jsonにユーザーIDを追記)
        if routes_to_add or routes_to_delete:
            logger.info(
                f"ユーザー'{line_user_id}'の路線情報が変更されました。S3のフラグファイルを更新します。"
            )
            s3_update_user_list(line_user_id)
        else:
            logger.info(
                f"ユーザー'{line_user_id}'の路線情報に変更がないため、S3フラグファイルの更新はスキップします。"
            )

    except ClientError as e:
        logger.error(
            f"DynamoDBへのユーザーデータ登録でエラーが発生しました: {e}", exc_info=True
        )
        raise


def s3_update_user_list(line_user_id: str):
    """S3のuser-list.jsonにユーザーIDが存在しない場合、追記してファイルを更新する。"""
    try:
        user_list = get_s3_object_as_list(S3_BUCKET_NAME, USER_LIST_FILE_KEY)

        if line_user_id not in user_list:
            user_list.append(line_user_id)
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=USER_LIST_FILE_KEY,
                Body=json.dumps(user_list, indent=2, ensure_ascii=False),
            )
            logger.info(
                f"S3ファイル'{USER_LIST_FILE_KEY}'にユーザーID'{line_user_id}'を追記しました。"
            )
        else:
            logger.info(
                f"ユーザーID'{line_user_id}'は既にS3ファイルに存在するため、更新はスキップします。"
            )

    except (ClientError, json.JSONDecodeError) as e:
        logger.error(
            f"S3へのユーザーリスト書き込みでエラーが発生しました: {e}", exc_info=True
        )
        # DynamoDBへの保存は成功しているので、ここでは例外を再送出しない


def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """Lambda関数のメインハンドラ。

    リクエストボディに'authorizationCode'が含まれていればLINEログイン処理、
    'lineUserId'が含まれていればユーザーデータの更新処理を行う。
    それ以外は不正なリクエストとして扱う。
    """
    try:
        body = json.loads(event.get("body") or "{}")
        logger.info("Received event", extra={"event_body": body})

        if "authorizationCode" in body:
            line_user_id = get_line_user_id(body)
            logger.info(
                f"LINEユーザーIDの取得に成功しました: {line_user_id}",
                extra={"line_user_id": line_user_id},
            )
            user_data = get_user_data(line_user_id)
            if not user_data:
                logger.info(
                    "新規ユーザーです。デフォルトデータを作成します。",
                    extra={"line_user_id": line_user_id},
                )
                user_data = {
                    "lineUserId": line_user_id,
                    "routes": [],
                }
            logger.info(
                "ユーザーデータの取得/作成に成功しました。レスポンスを返します。",
                extra={"user_data": user_data},
            )
            return {
                "statusCode": 200,
                "body": json.dumps(user_data, ensure_ascii=False, default=str),
            }
        elif "lineUserId" in body:
            post_user_data(body)
            line_user_id = body.get("lineUserId")
            logger.info(
                f"ユーザー情報を更新しました: {line_user_id}",
                extra={"line_user_id": line_user_id},
            )

            # SNSにユーザー登録通知を送信
            try:
                message = f"新しいユーザーが登録/更新されました。\nLINE User ID: {line_user_id}"
                subject = "【Train Delay Alert】ユーザー登録通知"
                sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN, Message=message, Subject=subject
                )
                logger.info("SNSにユーザー登録通知を送信しました。")
            except ClientError as e:
                logger.error(f"SNSへの通知送信に失敗しました: {e}", exc_info=True)

            return {
                "statusCode": 200,
                "body": json.dumps(body, ensure_ascii=False, default=str),
            }
        else:
            error_message = "不正なリクエストです。'authorizationCode'または'lineUserId'が含まれていません。"
            logger.error(error_message, extra={"event_body": body})
            return {"statusCode": 400, "body": json.dumps({"message": error_message})}
    except Exception as e:
        logger.critical("予期せぬエラーが発生しました", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"message": f"サーバー内部でエラーが発生しました1: {str(e)}"}
            ),
        }
