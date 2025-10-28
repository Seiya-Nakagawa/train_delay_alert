# -*- coding: utf-8 -*-
"""遅延情報をチェックするLambdaハンドラ.

EventBridgeからの定期的なトリガーを受け取り、対象の路線情報をYahoo路線情報から取得します。
遅延が発生している場合は、SNSにメッセージを発行してユーザーに通知します。
"""

import json
import os

import boto3
import requests
from boto3.dynamodb.conditions import Key  # query操作のためにKeyをインポート
from botocore.exceptions import ClientError

# --- 設定項目 ---
ODPT_ACCESS_TOKEN_PARAM_NAME = os.environ.get("ODPT_ACCESS_TOKEN_PARAM_NAME")
CHALLENGE_ACCESS_TOKEN_PARAM_NAME = os.environ.get("CHALLENGE_ACCESS_TOKEN_PARAM_NAME")
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
FLAG_FILE_KEY = "user-list.json"  # フラグファイルのS3キー
CACHE_FILE_KEY = "route-list.json"  # 路線リストキャッシュのS3キー
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
API_FILE_NAME = "api_url.json"
SAVE_PATH = "/tmp"
API_URL = [
    "https://api.odpt.org/api/v4/odpt:TrainInformation",
    "https://api-challenge.odpt.org/api/v4/odpt:TrainInformation",
]


# DynamoDBテーブルのキー設定
# パーティションキー (主キー)
PRIMARY_USER_KEY_NAME = "lineUserId"
# ソートキー (路線情報が格納されているカラム)
ROUTE_COLUMN_NAME = "settingOrRoute"
# ----------------------------------------------------

# Boto3クライアントの初期化 (ハンドラ外で定義すると再利用され効率的)
ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
user_table = dynamodb.Table(USER_TABLE_NAME)


# --- ヘルパー関数 ---
def get_ssm_parameter(ssm_param_name):
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print(f"Error getting parameter {ssm_param_name}: {e}")
        raise


api_url_token_pairs = []

for api_url in API_URL:
    if api_url == "https://api.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = ODPT_ACCESS_TOKEN_PARAM_NAME
    elif api_url == "https://api-challenge.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = CHALLENGE_ACCESS_TOKEN_PARAM_NAME
    else:
        print("パラメータストアからのデータ取得でエラーが発生しました")
        raise

    API_TOKEN = get_ssm_parameter(PARAM_NAME)
    api_url_token_pairs.append([api_url, API_TOKEN])

print("--- APIエンドポイントとトークン ---")
print(api_url_token_pairs)


def get_s3_object(bucket_name, key):
    try:
        response_s3flagfile = s3_client.get_object(Bucket=bucket_name, Key=key)

        file_content_string = response_s3flagfile["Body"].read().decode("utf-8")

        # ファイルが空文字列の場合は、空のリストを返す
        if not file_content_string.strip():
            print(f"S3ファイル '{key}' は空です。空のリストを返します。")
            return []

        # JSON文字列をPythonオブジェクト（リスト）に変換
        s3_object_list = json.loads(file_content_string)

        # 念のため、変換後のオブジェクトがリスト型かチェック
        if not isinstance(s3_object_list, list):
            print(
                f"警告: S3ファイル '{key}' はJSONですが、リスト形式ではありません。空のリストを返します。"
            )
            return []

        return s3_object_list
    except ClientError as e:
        # エラーコードをチェックする
        if e.response["Error"]["Code"] == "NoSuchKey":
            # ファイルが存在しない場合のエラー
            print(f"オブジェクト '{key}' は存在しませんでした。")
            return None
        else:
            # 権限エラーなど、その他の予期せぬS3エラー
            print(f"S3アクセス中に予期せぬエラーが発生しました: {e}")
            raise  # このエラーはここで処理せず、呼び出し元に投げる


def get_line_list(lineuserid_list):
    """
    複数のユーザーIDリストに基づき、DynamoDBから各ユーザーの路線情報を取得する。
    複合主キーを持つテーブルのため、query操作を使用する。

    Args:
        lineuserid_list (list): 路線情報を取得したいlineUserIdのリスト。

    Returns:
        list: 取得した路線情報の辞書のリスト。
              例: [{'lineUserId': 'U123...', 'settingOrRoute': 'JR山手線'}, ...]
    """
    if not lineuserid_list:
        return []

    user_route_list = []
    print(f"これから {len(lineuserid_list)} 人のユーザーの路線情報を取得します。")

    # ユーザーIDのリストをループして、一人ずつqueryを実行
    for user_id in lineuserid_list:
        try:
            print(f"ユーザー '{user_id}' のデータをクエリしています...")

            # query操作を実行: 指定したパーティションキーに紐づく項目を全て取得
            response = user_table.query(
                KeyConditionExpression=Key(PRIMARY_USER_KEY_NAME).eq(user_id)
            )

            # 取得したアイテムの中から、路線情報だけを抽出
            # settingOrRouteが'#PROFILE#'で始まらないものを路線情報とみなす
            route_list = [
                item[ROUTE_COLUMN_NAME]
                for item in response.get("Items", [])
                if not item.get(ROUTE_COLUMN_NAME, "").startswith("#PROFILE#")
            ]

            if route_list:
                print(f"  -> {len(route_list)} 件の路線情報が見つかりました。")
                user_route_list.extend(route_list)
            else:
                print("  -> 路線情報は見つかりませんでした。")

        except ClientError as e:
            print(
                f"ユーザー '{user_id}' のデータ取得中にエラーが発生しました: {e.response['Error']['Message']}"
            )
            # 一人のユーザーでエラーが発生しても、他のユーザーの処理を続ける
            continue

    user_route_list = list(set(user_route_list))
    print(f"対象ユーザの全路線情報（重複は排除）: {user_route_list}")

    return user_route_list


def get_realtime_train_information():
    """リアルタイム運行情報APIを呼び出し、全路線の現在の運行状況を取得する。"""
    try:
        realtime_data = []
        API_TOKEN = "gut723ueywfj6rkwvfi86skmz3yg5a4tt6sf974k1xinkkg1cormvfunb9xpgskw"

        # 2. リクエストパラメータの設定
        # odpt:operator に相模鉄道を指定します
        for api_url in API_URL:
            print(f"APIエンドポイント: {api_url}")
            # check_url = api_url + API_TOKEN
            params = {"acl:consumerKey": API_TOKEN}

            response = requests.get(api_url, params=params)
            print("response")
            print(response.json())
            response.raise_for_status()
            realtime_data.extend(response.json())

        print("\n--- 取得した運行情報 ---")
        print(realtime_data)
    except requests.exceptions.RequestException as e:
        print(f"エラー: APIへのリクエストに失敗しました。\n{e}")
        return None


def lambda_handler(event, context):
    """Lambda関数のメインハンドラ."""
    try:
        # S3フラグファイルの中身をチェック（ファイル内のユーザIDを確認）
        s3_route_list = get_s3_object(S3_BUCKET_NAME, CACHE_FILE_KEY)
        lineuserid_list = get_s3_object(S3_BUCKET_NAME, FLAG_FILE_KEY)

        if lineuserid_list is not None:
            print(
                f"[INFO]フラグファイルから {len(lineuserid_list)} 件のユーザーIDを読み込みました: {lineuserid_list}"
            )

            # DynamoDBから路線リストを取得
            user_route_list = get_line_list(lineuserid_list)
            route_list = list(set(user_route_list + s3_route_list))
            route_string = json.dumps(route_list, indent=2, ensure_ascii=False)

            s3_client.put_object(
                Bucket=S3_BUCKET_NAME, Key=CACHE_FILE_KEY, Body=route_string
            )

        # with open(API_FILE_NAME, "r", encoding="utf-8") as f:
        #     api_data = json.load(f)

        get_realtime_train_information()

        # found_url = None

        # for route in route_list:
        #     for api_item in api_data:
        #         if api_item.get("route") == route:
        #             api_url = api_item.get("url")
        #             check_delay_route(api_url)
        #             route = api_data.get("route")
        #         break

        return {
            "statusCode": 200,
            "body": json.dumps("Process finished successfully."),
        }
    except Exception as e:
        print(f"ERROR: 予期せぬエラーが発生しました: {e}")
        return {"statusCode": 500, "body": json.dumps(str(e))}
