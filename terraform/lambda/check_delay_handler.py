# -*- coding: utf-8 -*-
"""遅延情報をチェックするLambdaハンドラ.

EventBridgeからの定期的なトリガーを受け取り、対象の路線情報をYahoo路線情報から取得します。
遅延が発生している場合は、SNSにメッセージを発行してユーザーに通知します。
"""

import json
import logging
import os

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# --- ログ設定 ---
# ログレベルを環境変数から取得、なければINFO
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
# ルートロガーを取得し、レベルを設定
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# --- AWSリソース設定 ---
# 環境変数から設定値を取得
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_ACCESS_TOKEN_PARAM_NAME = os.environ.get("LINE_ACCESS_TOKEN_PARAM_NAME")
ODPT_ACCESS_TOKEN_PARAM_NAME = os.environ.get("ODPT_ACCESS_TOKEN_PARAM_NAME")
CHALLENGE_ACCESS_TOKEN_PARAM_NAME = os.environ.get("CHALLENGE_ACCESS_TOKEN_PARAM_NAME")
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
NG_WORD = os.environ.get("NG_WORD")

# --- S3オブジェクトキー設定 ---
USER_LIST_FILE_KEY = "user-list.json"  # 処理対象のユーザーリストが格納されたS3キー
ROUTE_LIST_FILE_KEY = "route-list.json"  # 全ユーザーの登録路線リスト
DELAY_MESSAGES_FILE_KEY = "delay-messages.json"  # 現在遅延中の路線リストのキャッシュ

RAILWAY_LIST_FILE_NAME = "railway_list.json"

# --- DynamoDBテーブルキー設定 ---
PRIMARY_USER_KEY_NAME = "lineUserId"  # ユーザーIDを保持するパーティションキー
ROUTE_COLUMN_NAME = "settingOrRoute"  # 路線情報を格納するソートキー

# --- 外部API設定 ---
LINE_PUSH_API_URL = "https://api.line.me/v2/bot/message/push"
# 運行情報APIのエンドポイントリスト
LINE_API_URL = [
    "https://api.odpt.org/api/v4/odpt:TrainInformation",
    "https://api-challenge.odpt.org/api/v4/odpt:TrainInformation",
]

# --- Boto3クライアントの初期化 ---
# Lambdaの実行環境外で初期化することで、呼び出し間でクライアントを再利用し、パフォーマンスを向上させる
ssm_client = boto3.client("ssm")
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
user_table = dynamodb.Table(USER_TABLE_NAME)


def get_ssm_parameter(ssm_param_name):
    """SSMパラメータストアから指定されたパラメータの値を取得する.

    Args:
        ssm_param_name (str): 取得するパラメータの名前。

    Returns:
        str: パラメータの値。

    Raises:
        ClientError: パラメータの取得中にAWS APIエラーが発生した場合。
    """
    logger.info(f"SSMからパラメータ'{ssm_param_name}'を取得します。")
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        logger.error(f"パラメータ {ssm_param_name} の取得に失敗しました: {e}")
        raise


# --- グローバル変数の初期化 ---
# 外部APIの認証情報をSSMから取得
LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_ACCESS_TOKEN_PARAM_NAME)
api_url_token_pairs = []

logger.info("運行情報APIのアクセストークンをSSMから読み込んでいます。")
for api_url in LINE_API_URL:
    if api_url == "https://api.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = ODPT_ACCESS_TOKEN_PARAM_NAME
    elif api_url == "https://api-challenge.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = CHALLENGE_ACCESS_TOKEN_PARAM_NAME
    else:
        # 設定にないAPI URLが指定された場合はエラー
        logger.error("無効なAPI URLが設定されています。", extra={"url": api_url})
        raise ValueError("LINE_API_URLリストに無効なAPI URLが含まれています。")

    API_TOKEN = get_ssm_parameter(PARAM_NAME)
    api_url_token_pairs.append([api_url, API_TOKEN])
logger.info("APIトークンの読み込みが完了しました。")


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
    logger.info(f"S3オブジェクトを取得します。", extra={"bucket": bucket_name, "key": key})
    try:
        response_s3flagfile = s3_client.get_object(Bucket=bucket_name, Key=key)
        file_content_string = response_s3flagfile["Body"].read().decode("utf-8")

        # ファイルが空かチェック
        if not file_content_string.strip():
            logger.warning(f"S3ファイル'{key}'は空です。空のリストを返します。", extra={"bucket": bucket_name, "key": key})
            return []

        s3_object_list = json.loads(file_content_string)

        # 内容がリスト形式かチェック
        if not isinstance(s3_object_list, list):
            logger.warning(
                f"S3ファイル'{key}'はJSONリスト形式ではありません。空のリストを返します。",
                extra={"bucket": bucket_name, "key": key}
            )
            return []

        logger.info(
            f"S3オブジェクト'{key}'から {len(s3_object_list)} 件の項目を読み込みました。",
            extra={"bucket": bucket_name, "key": key, "item_count": len(s3_object_list)}
        )
        return s3_object_list
    except ClientError as e:
        # オブジェクトが存在しない場合は正常なケースとしてNoneを返す
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info(f"S3オブジェクト'{key}'が見つかりませんでした。", extra={"bucket": bucket_name, "key": key})
            return None
        else:
            # その他のAWSエラーは例外を再送出
            logger.error(f"S3へのアクセス中に予期せぬエラーが発生しました: {e}", extra={"bucket": bucket_name, "key": key})
            raise


def get_line_list(s3_lineuserid_list):
    """複数のユーザーIDに基づき、DynamoDBから各ユーザーが設定した路線情報を取得する.

    Args:
        s3_lineuserid_list (list): 路線情報を取得したいLINEユーザーIDのリスト。

    Returns:
        list: 全ユーザーの路線情報を一意に集約したリスト。
    """
    if not s3_lineuserid_list:
        logger.info("ユーザーIDリストが空のため、DynamoDBのクエリをスキップします。")
        return []

    user_route_list = []
    logger.info(f"DynamoDBから {len(s3_lineuserid_list)} 人のユーザーの路線情報取得を開始します。")

    for user_id in s3_lineuserid_list:
        try:
            logger.debug(f"ユーザー'{user_id}'のデータをクエリしています...")
            # パーティションキーでユーザーの項目を全て取得
            response = user_table.query(
                KeyConditionExpression=Key(PRIMARY_USER_KEY_NAME).eq(user_id)
            )

            # ユーザー設定項目(#PROFILE#)を除外し、路線情報のみを抽出
            route_list = [
                item[ROUTE_COLUMN_NAME]
                for item in response.get("Items", [])
                if not item.get(ROUTE_COLUMN_NAME, "").startswith("#PROFILE#")
            ]

            if route_list:
                logger.debug(f"ユーザー'{user_id}'の路線が {len(route_list)} 件見つかりました。", extra={"user_id": user_id, "route_count": len(route_list)})
                user_route_list.extend(route_list)
            else:
                logger.debug(f"ユーザー'{user_id}'の路線は見つかりませんでした。", extra={"user_id": user_id})

        except ClientError as e:
            logger.error(
                f"ユーザー'{user_id}'のデータ取得に失敗しました: {e.response['Error']['Message']}",
                extra={"user_id": user_id}
            )
            continue  # エラーが発生したユーザーはスキップして処理を続行

    # 全ユーザーの路線リストから重複を排除
    unique_user_route_list = list(set(user_route_list))
    logger.info(
        f"全ユーザーから合計 {len(unique_user_route_list)} 件のユニークな路線が見つかりました。",
        extra={"unique_route_count": len(unique_user_route_list)}
    )
    logger.debug(f"ユニークな路線リスト: {unique_user_route_list}")

    return unique_user_route_list


def get_realtime_train_information():
    """リアルタイム運行情報APIを呼び出し、全路線の現在の運行状況を取得する.

    設定された複数のAPIエンドポイントから情報を収集し、結果を一つのリストに結合する。

    Returns:
        list | None: 全路線の運行情報のリスト。APIリクエストに失敗した場合はNone。
    """
    logger.info("全てのAPIエンドポイントからリアルタイム運行情報を取得します...")
    try:
        realtime_data_list = []
        for url, token in api_url_token_pairs:
            logger.info(f"APIエンドポイントを呼び出します: {url}")
            params = {"acl:consumerKey": token}

            response = requests.get(url, params=params)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生させる

            response_data = response.json()
            realtime_data_list.extend(response_data)
            logger.debug(f"{len(response_data)} 件のレコードを取得しました。", extra={"url": url, "record_count": len(response_data)})

        logger.info(
            f"取得完了。合計 {len(realtime_data_list)} 件のレコードを取得しました。",
            extra={"total_record_count": len(realtime_data_list)}
        )
        return realtime_data_list

    except requests.exceptions.RequestException as e:
        logger.error("APIへのリクエストに失敗しました。", exc_info=True)
        return None


def create_snd_message(user_route, message):
    """遅延情報を示すLINE Flex MessageのJSONオブジェクトを生成する.

    Args:
        user_route (str): 路線名 (例: "JR山手線")。
        message (str): 運行情報の詳細テキスト。

    Returns:
        dict: LINE Flex MessageのJSONオブジェクト。
    """
    logger.info(f"路線'{user_route}'のFlex Messageを作成します。", extra={"user_route": user_route})
    # LINEのFlex Message Simulatorで作成したJSONをテンプレートとして使用
    message_object = {
        "type": "flex",
        "altText": f"{user_route}の運行情報",
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
    return message_object


def snd_line_message(user_id, message_object):
    """指定されたユーザーIDにLINE Pushメッセージを送信する.

    Args:
        user_id (str): 送信先のLINEユーザーID ('U'から始まる文字列)。
        message_object (dict): 送信するメッセージオブジェクト (Flex Messageなど)。

    Returns:
        bool: 送信が成功した場合はTrue、失敗した場合はFalse。
    """
    logger.info(f"ユーザー'{user_id}'にLINEメッセージを送信します...", extra={"user_id": user_id})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_SECRET}",
    }

    # LINE Push APIのリクエストボディを作成
    payload = {"to": user_id, "messages": [message_object]}

    try:
        response = requests.post(
            LINE_PUSH_API_URL, headers=headers, data=json.dumps(payload)
        )
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる

        logger.info(
            f"メッセージの送信に成功しました。",
            extra={"user_id": user_id, "status_code": response.status_code}
        )
        return True

    except requests.exceptions.RequestException as e:
        logger.error("LINEへのメッセージ送信に失敗しました。", extra={"user_id": user_id}, exc_info=True)
        return False


def delay_check(user_route_list, realtime_data_list, railway_list, s3_delay_list):
    # アクティブユーザーが設定した各路線について遅延をチェック
    new_delay_messages_list = []
    id_to_name_map = {item["odpt:railway"]: item["route"] for item in railway_list}
    ng_words = [word.strip() for word in NG_WORD.split(',')] if NG_WORD else []

    logger.info(f"アクティブユーザーの {len(user_route_list)} 件の路線の処理を開始します。")
    for user_route_id in user_route_list:
        user_route_name = id_to_name_map.get(user_route_id)
        if not user_route_name:
            logger.warning(
                f"''{user_route_id}''に一致する鉄道名が見つかりませんでした。スキップします。",
                extra={"user_route_id": user_route_id},
            )
            continue

        logger.debug(f"--- 路線'{user_route_name}'の処理を開始 ---", extra={"user_route": user_route_name})
        send_flg = False
        message = None

        # 鉄道名に一致するリアルタイム運行情報を検索
        for realtime_data in realtime_data_list:
            if realtime_data["odpt:railway"] == user_route_id:
                message = realtime_data["odpt:trainInformationText"]["ja"]
                break
        if not message:
            logger.warning(
                f"鉄道名'{user_route_id}'のリアルタイム情報が見つかりませんでした。スキップします。",
                extra={"railway_name": user_route_id}
            )
            continue
        logger.debug(f"運行情報メッセージが見つかりました: '{message}'", extra={"railway_name": user_route_id, "message": message})

        # 取得した運行情報が、既に通知済のメッセージかチェック
        is_new_message = True
        for delay_message in s3_delay_list:
            if delay_message.get("messages") == message:
                is_new_message = False
                logger.info(
                    "このメッセージは既に通知済みです。スキップします。",
                    extra={"message": message}
                )
                break
        
        if is_new_message:
            # 遅延のメッセージ内容かチェック
            is_delay = False
            if ng_words:
                for ng_word in ng_words:
                    if ng_word in message:
                        is_delay = True
                        break
            else: # NG_WORDが設定されてなければ、新しいメッセージはすべて遅延とみなす
                is_delay = True

            if is_delay:
                send_flg = True

        # 通知フラグがTrueの場合、通知処理を実行
        if send_flg:
            logger.info(
                "新規の遅延またはステータス変更を検知しました。通知の準備をします。",
                extra={"user_route": user_route_name, "message": message}
            )

            message_object = create_snd_message(user_route_name, message)

            # パーティションキーでユーザーの項目を全て取得
            response = user_table.query(
                IndexName="route-index",
                KeyConditionExpression=Key(ROUTE_COLUMN_NAME).eq(user_route_id),
            )

            user_list = [
                item[PRIMARY_USER_KEY_NAME] for item in response.get("Items", [])
            ]

            for user_id in user_list:
                snd_line_message(user_id, message_object)

            new_delay_message = {"route": user_route_name, "messages": message}
            new_delay_messages_list.append(new_delay_message)

    return new_delay_messages_list


def lambda_handler(event, context):
    """Lambda関数のメインハンドラ.

    EventBridgeからのトリガーを受け、以下の処理を実行する。
    1. S3から設定ファイル（路線リスト、ユーザIDリスト）を読み込む。
    2. 1で取得したユーザIDに基づき、DynamoDBから各ユーザが設定した路線情報を取得する。
    3. 1と2の路線情報を統合し、S3にキャッシュとして保存する。
    4. 交通情報APIからリアルタイムの運行情報を取得する。
    5. ユーザが設定した路線に遅延が発生しているか判定する。
    6. 新規の遅延が発生している場合、対象ユーザにLINEで通知する。

    Args:
        event (dict): Lambdaに渡されるイベントデータ (今回は未使用)。
        context (object): Lambdaの実行コンテキスト情報 (今回は未使用)。

    Returns:
        dict: 処理結果を示すステータスコードとメッセージを含む辞書。
    """
    try:
        # --- 1. 処理対象の路線リストの準備 ---
        # S3キャッシュとDynamoDBから最新の路線リストを構築する

        # S3にキャッシュされた全ユーザーの路線リストを取得
        s3_route_list = get_s3_object(S3_BUCKET_NAME, ROUTE_LIST_FILE_KEY) or []
        # 直近で設定変更のあったユーザーリストを取得
        s3_lineuserid_list = get_s3_object(S3_BUCKET_NAME, USER_LIST_FILE_KEY) or []
        # 直近の遅延情報リスト
        s3_delay_list = get_s3_object(S3_BUCKET_NAME, DELAY_MESSAGES_FILE_KEY) or []

        if not s3_lineuserid_list:
            logger.info("フラグファイルにユーザーIDが見つかりませんでした。S3キャッシュの路線のみ使用します。")
            user_route_list = []
        else:
            # 設定変更のあったユーザーの路線情報をDynamoDBから取得
            logger.info(f"{len(s3_lineuserid_list)} 件のユーザーIDを読み込みました。DynamoDBから路線情報を取得します。")
            user_route_list = get_line_list(s3_lineuserid_list)
            # DynamoDBから取得したリストとS3キャッシュをマージし、最新の状態でS3に保存
            s3_route_list = list(set(user_route_list + s3_route_list))

        route_string = json.dumps(s3_route_list, indent=2, ensure_ascii=False)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME, Key=ROUTE_LIST_FILE_KEY, Body=route_string
        )
        logger.info(f"統合後の路線リストをS3キャッシュ'{ROUTE_LIST_FILE_KEY}'に保存しました。")

        # --- 3. リアルタイム運行情報の取得 ---
        realtime_data_list = get_realtime_train_information()
        if realtime_data_list is None:
            raise Exception("リアルタイム運行情報の取得に失敗しました。")

        # --- 4. マッピングと遅延判定の準備 ---
        # ローカルのJSONファイルから路線マッピングと無視するメッセージリストを読み込む
        with open(RAILWAY_LIST_FILE_NAME, "r", encoding="utf-8") as f:
            railway_list = json.load(f)
        logger.info(f"{len(railway_list)} 件の路線・鉄道マッピングを読み込みました。", extra={"mapping_count": len(railway_list)})

        # --- 5. 遅延判定と通知処理 ---
        new_delay_messages_list = delay_check(
            user_route_list, realtime_data_list, railway_list, s3_delay_list
        )

        if new_delay_messages_list:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=DELAY_MESSAGES_FILE_KEY,
                Body=new_delay_messages_list,
            )
        else:
            s3_client.delete_object(
                Bucket=S3_BUCKET_NAME,
                Key=DELAY_MESSAGES_FILE_KEY,
            )

        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=USER_LIST_FILE_KEY,
        )

        logger.info("== Lambdaハンドラの処理が正常に終了しました。 ==")
        return {
            "statusCode": 200,
            "body": json.dumps("Process finished successfully.", ensure_ascii=False),
        }
    except Exception as e:
        # ハンドラ全体で予期せぬエラーをキャッチし、ログに出力
        logger.critical("lambda_handlerで予期せぬエラーが発生しました", exc_info=True)
        return {"statusCode": 500, "body": json.dumps(str(e), ensure_ascii=False)}
