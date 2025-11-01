# -*- coding: utf-8 -*-
import json
import logging
import os

import boto3
import requests
from botocore.exceptions import ClientError

# --- ログ設定 ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# --- グローバル変数・初期設定 ---
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get("LINE_CHANNEL_SECRET_PARAM_NAME")
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL")
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
USER_LIST_FILE_KEY = "user-list.json"

LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
PROFILE_KEY = "#PROFILE#"

ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USER_TABLE_NAME)

# --- ヘルパー関数 ---


def get_ssm_parameter(ssm_param_name):
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError:
        logger.error(
            f"パラメータ {ssm_param_name} の取得に失敗しました。", exc_info=True
        )
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
    print("test2")
    print(response)

    # ステータスコードが200番台でない場合にエラーログを出力
    if not response.ok:
        logger.error(
            "LINE APIへのリクエストでエラーが発生しました。",
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
    verify_response = requests.post(
        LINE_VERIFY_URL, data={"id_token": id_token, "client_id": LINE_CHANNEL_ID}
    )
    # ステータスコードが200番台でない場合にエラーログを出力
    if not verify_response.ok:
        logger.error(
            "LINE API(verify)へのリクエストでエラーが発生しました。",
            extra={
                "status_code": verify_response.status_code,
                "response_body": verify_response.text,
            },
        )
    verify_response.raise_for_status()
    verify_json = verify_response.json()
    line_user_id = verify_json.get("sub")
    if not line_user_id:
        raise ValueError("LINEユーザIDの取得に失敗しました。")
    return line_user_id


def get_user_data(line_user_id):
    try:
        # railway_list.jsonを読み込んで、IDと路線のマッピングを作成
        with open("railway_list.json", "r", encoding="utf-8") as f:
            railway_list = json.load(f)
        railway_map = {item["odpt:railway"]: item["route"] for item in railway_list}

        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("lineUserId").eq(
                line_user_id
            )
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

        # 路線IDを路線名に変換
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


def get_s3_object(bucket_name, key):
    """S3から指定されたオブジェクトを取得し、内容をPythonのリストとして返す.

    オブジェクトが存在しない場合はNoneを、ファイルが空または不正なJSON形式の場合は
    空のリストを返す。

    Args:
        bucket_name (str): S3バケット名。
        key (str): S3オブジェクトのキー。

    Returns:
        list | None: オブジェクトの内容をデコードしたリスト。
                      オブジェクトが存在しない場合はNone。
                      ファイルが空、またはJSONリスト形式でない場合は空のリスト。

    Raises:
        ClientError: S3へのアクセス中に'NoSuchKey'以外の予期せぬエラーが発生した場合。
    """
    logger.info(
        "S3オブジェクトを取得します。", extra={"bucket": bucket_name, "key": key}
    )
    try:
        response_s3flagfile = s3_client.get_object(Bucket=bucket_name, Key=key)
        file_content_string = response_s3flagfile["Body"].read().decode("utf-8")

        # ファイルが空かチェック
        if not file_content_string.strip():
            logger.warning(
                f"S3ファイル'{key}'は空です。空のリストを返します。",
                extra={"bucket": bucket_name, "key": key},
            )
            return []

        s3_object_list = json.loads(file_content_string)

        # 内容がリスト形式かチェック
        if not isinstance(s3_object_list, list):
            logger.warning(
                f"S3ファイル'{key}'はJSONリスト形式ではありません。空のリストを返します。",
                extra={"bucket": bucket_name, "key": key},
            )
            return []

        logger.info(
            f"S3オブジェクト'{key}'から {len(s3_object_list)} 件の項目を読み込みました。",
            extra={
                "bucket": bucket_name,
                "key": key,
                "item_count": len(s3_object_list),
            },
        )
        return s3_object_list
    except ClientError as e:
        # オブジェクトが存在しない場合は正常なケースとしてNoneを返す
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info(
                f"S3オブジェクト'{key}'が見つかりませんでした。",
                extra={"bucket": bucket_name, "key": key},
            )
            return None
        else:
            # その他のAWSエラーは例外を再送出
            logger.error(
                f"S3へのアクセス中に予期せぬエラーが発生しました: {e}",
                extra={"bucket": bucket_name, "key": key},
            )
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

        # 路線情報に変更があった場合のみS3に通知
        if routes_to_add or routes_to_delete:
            logger.info(
                f"ユーザー'{line_user_id}'の路線情報が変更されたため、S3に通知します。",
                extra={"line_user_id": line_user_id},
            )
            # S3のuser-list.jsonにユーザーIDを追記
            try:
                # 既存のリストを取得、なければ新規作成
                user_list = get_s3_object(S3_BUCKET_NAME, USER_LIST_FILE_KEY) or []

                # ユーザーIDがリストになければ追加
                if line_user_id not in user_list:
                    user_list.append(line_user_id)
                    logger.info(
                        f"ユーザーID'{line_user_id}'をS3ファイルに追加します。",
                        extra={"line_user_id": line_user_id},
                    )

                    # 更新したリストをS3に書き戻す
                    user_list_string = json.dumps(
                        user_list, indent=2, ensure_ascii=False
                    )
                    s3_client.put_object(
                        Bucket=S3_BUCKET_NAME,
                        Key=USER_LIST_FILE_KEY,
                        Body=user_list_string,
                    )
                    logger.info(
                        f"S3ファイル'{USER_LIST_FILE_KEY}'を更新しました。",
                        extra={"file_key": USER_LIST_FILE_KEY},
                    )
                else:
                    logger.info(
                        f"ユーザーID'{line_user_id}'は既にリストに存在するため、S3ファイルの更新はスキップします。",
                        extra={"line_user_id": line_user_id},
                    )

            except Exception as e:
                logger.error(
                    f"S3へのユーザーリスト書き込みでエラーが発生しました: {e}",
                    exc_info=True,
                )
                # DynamoDBへの保存は成功しているので、ここでは例外を再送出しない
        else:
            logger.info(
                f"ユーザー'{line_user_id}'の路線情報に変更がないため、S3通知はスキップします。",
                extra={"line_user_id": line_user_id},
            )

    except ClientError as e:
        logger.error(
            f"DynamoDBへのユーザーデータ登録でエラーが発生しました: {e}", exc_info=True
        )
        raise


def s3_update_user_list(line_user_id):
    """S3のuser-list.jsonにユーザーIDを追記します。

    Args:
        line_user_id (str): 追加するLINEユーザーID。
    """
    try:
        # 既存のリストを取得、なければ新規作成
        user_list = get_s3_object(S3_BUCKET_NAME, USER_LIST_FILE_KEY) or []

        # ユーザーIDがリストになければ追加
        if line_user_id not in user_list:
            user_list.append(line_user_id)
            logger.info(
                f"ユーザーID'{line_user_id}'をS3ファイルに追加します。",
                extra={"line_user_id": line_user_id},
            )

            # 更新したリストをS3に書き戻す
            user_list_string = json.dumps(user_list, indent=2, ensure_ascii=False)
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=USER_LIST_FILE_KEY,
                Body=user_list_string,
            )
            logger.info(
                f"S3ファイル'{USER_LIST_FILE_KEY}'を更新しました。",
                extra={"file_key": USER_LIST_FILE_KEY},
            )
        else:
            logger.info(
                f"ユーザーID'{line_user_id}'は既にリストに存在するため、S3ファイルの更新はスキップします。",
                extra={"line_user_id": line_user_id},
            )

    except Exception as e:
        logger.error(
            f"S3へのユーザーリスト書き込みでエラーが発生しました: {e}",
            exc_info=True,
        )
        # この関数は他の処理から呼び出されることを想定し、
        # エラーが発生してもメインの処理は続行できるように例外は再送出しない。


# --- メインハンドラ (変更なし) ---
def lambda_handler(event, context):
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

            s3_update_user_list(line_user_id)

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
                {"message": f"サーバー内部でエラーが発生しました: {str(e)}"}
            ),
        }
