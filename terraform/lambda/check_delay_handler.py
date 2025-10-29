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
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get("LINE_CHANNEL_SECRET_PARAM_NAME")
ODPT_ACCESS_TOKEN_PARAM_NAME = os.environ.get("ODPT_ACCESS_TOKEN_PARAM_NAME")
CHALLENGE_ACCESS_TOKEN_PARAM_NAME = os.environ.get("CHALLENGE_ACCESS_TOKEN_PARAM_NAME")
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
FLAG_FILE_KEY = "user-list.json"  # フラグファイルのS3キー
CACHE_FILE_KEY = "route-list.json"  # 登録されている路線リストキャッシュのS3キー
DELAY_FILE_KEY = "delay-list.json"  # 遅延中の路線リストキャッシュのS3キー
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
API_FILE_NAME = "api_url.json"
SAVE_PATH = "/tmp"
NG_WORD = os.environ.get("NG_WORD")
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


LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_CHANNEL_SECRET_PARAM_NAME)
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
        realtime_data_list = []

        # 2. リクエストパラメータの設定
        # odpt:operator に相模鉄道を指定します
        for url, token in api_url_token_pairs:
            print(f"APIエンドポイント: {url}")
            # check_url = api_url + API_TOKEN
            params = {"acl:consumerKey": token}

            response = requests.get(url, params=params)
            print("response")
            print(response.json())
            response.raise_for_status()
            realtime_data_list.extend(response.json())

        return realtime_data_list

    except requests.exceptions.RequestException as e:
        print(f"エラー: APIへのリクエストに失敗しました。\n{e}")
        return None


def send_line_message(user_id, message_object):
    """
    指定されたユーザーIDにLINEメッセージを送信する。

    Args:
        user_id (str): 送信先のLINEユーザーID ('U'から始まる文字列)
        message_object (dict): 送信するメッセージオブジェクト (テキストまたはFlex Message)

    Returns:
        bool: 送信が成功した場合はTrue、失敗した場合はFalse
    """
    print(f"ユーザー '{user_id}' にメッセージを送信します...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {"to": user_id, "messages": [message_object]}

    try:
        response = requests.post(
            LINE_PUSH_API_URL, headers=headers, data=json.dumps(payload)
        )
        # ステータスコードが200番台でない場合に例外を発生させる
        response.raise_for_status()

        print(f"メッセージの送信に成功しました。 Status Code: {response.status_code}")
        return True

    except requests.exceptions.RequestException as e:
        print("エラー: LINEへのメッセージ送信に失敗しました。")
        # APIからのエラーレスポンス詳細を表示
        if e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        else:
            print(f"Error Details: {e}")
        return False


def create_snd_message(user_route, message):
    """
    遅延情報を示すFlex MessageのJSONオブジェクトを作成する。

    Args:
        route_name (str): 路線名 (例: "JR山手線")
        information_text (str): 運行情報の詳細テキスト

    Returns:
        dict: LINE Flex MessageのJSONオブジェクト
    """
    # LINE Flex Message Simulator (https://developers.line.biz/flex-simulator/)
    # を使うと、このようなJSONを簡単にデザイン・作成できます。
    snd_message = {
        "type": "flex",
        "altText": f"{user_route}の運行情報",  # 通知に表示されるテキスト
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "⚠️ 列車遅延情報",
                        "color": "#ffffff",
                        "weight": "bold",
                        "size": "md",
                    }
                ],
                "backgroundColor": "#FF6B6B",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": user_route,
                        "weight": "bold",
                        "size": "xl",
                        "margin": "md",
                    },
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": message,
                                "wrap": True,
                                "color": "#555555",
                                "size": "sm",
                            }
                        ],
                    },
                ],
            },
        },
    }
    return snd_message


def snd_line_message(user_id, message_object):
    """
    指定されたユーザーIDにLINEメッセージを送信する。

    Args:
        user_id (str): 送信先のLINEユーザーID ('U'から始まる文字列)
        message_object (dict): 送信するメッセージオブジェクト (テキストまたはFlex Message)

    Returns:
        bool: 送信が成功した場合はTrue、失敗した場合はFalse
    """
    print(f"ユーザー '{user_id}' にメッセージを送信します...")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_SECRET}",
    }

    payload = {"to": user_id, "messages": [message_object]}

    try:
        response = requests.post(
            LINE_PUSH_API_URL, headers=headers, data=json.dumps(payload)
        )
        # ステータスコードが200番台でない場合に例外を発生させる
        response.raise_for_status()

        print(f"メッセージの送信に成功しました。 Status Code: {response.status_code}")
        return True

    except requests.exceptions.RequestException as e:
        print("エラー: LINEへのメッセージ送信に失敗しました。")
        # APIからのエラーレスポンス詳細を表示
        if e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        else:
            print(f"Error Details: {e}")
        return False


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

        realtime_data_list = get_realtime_train_information()

        with open("route_railway_list.json", "r", encoding="utf-8") as f:
            route_railway_string = f.read()

        route_railway_list = json.loads(route_railway_string)

        with open("delay_messages.json", "r", encoding="utf-8") as f:
            delay_messages_string = f.read()

        delay_messages_list = json.loads(delay_messages_string)

        notification_list = []

        # 対象の路線を1件ごと処理
        for user_route in user_route_list:
            send_flg = True
            railway_name = None
            message = None
            # route_railway_list.jsonで一致する路線名の"odpt:railway"を取得
            for route_railway in route_railway_list:
                if route_railway["route"] == user_route:
                    railway_name = route_railway["odpt:railway"]
                    break

            # route_railway_list.jsonに路線がない場合はエラー
            if railway_name is None:
                return {
                    "statusCode": 401,
                    "body": json.dumps("ERROR: "),
                }

            # API取得したリアルタイム路線情報を１件ずつ抽出
            for realtime_data in realtime_data_list:
                if realtime_data["odpt:railway"] == railway_name:
                    message = realtime_data["odpt:trainInformationText"]["ja"]
                    break

            if message is None:
                return {
                    "statusCode": 402,
                    "body": json.dumps("ERROR: "),
                }

            for delay_message in delay_messages_list:
                if delay_message["message"] == message:
                    send_flg = False
                    break

            if send_flg is True:
                for ng_word in NG_WORD:
                    if ng_word in message:
                        # query操作を実行: 指定したパーティションキーに紐づく項目を全て取得
                        response_snd_user = user_table.query(
                            KeyConditionExpression=Key(ROUTE_COLUMN_NAME).eq(user_route)
                        )

                # query操作を実行: 指定したパーティションキーに紐づく項目を全て取得
                response_snd_user = user_table.query(
                    eyConditionExpression=Key(ROUTE_COLUMN_NAME).eq(user_route)
                )

                print("response_snd_user")
                print(response_snd_user)

                # route_list = [
                # item[ROUTE_COLUMN_NAME]
                # for item in response.get("Items", [])
                # if not item.get(ROUTE_COLUMN_NAME, "").startswith("#PROFILE#")

                # 送信するFlex Messageを生成
                # snd_message = create_snd_message(user_route, message)

                # LINEにメッセージを送信
                # snd_line_message(snd_message)
                break

        return {
            "statusCode": 200,
            "body": json.dumps("Process finished successfully."),
        }
    except Exception as e:
        print(f"ERROR: 予期せぬエラーが発生しました: {e}")
        return {"statusCode": 500, "body": json.dumps(str(e))}
