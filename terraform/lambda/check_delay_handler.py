# -*- coding: utf-8 -*-
"""遅延情報をチェックするLambdaハンドラ.

EventBridgeからの定期的なトリガーを受け取り、対象の路線情報をYahoo路線情報から取得します。
遅延が発生している場合は、SNSにメッセージを発行してユーザーに通知します。
"""

import json
import os

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

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
ROUTE_LIST_FILE_KEY = "route-list.json"  # 全ユーザーの登録路線リストのキャッシュ
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
    print(f"情報: SSMからパラメータ'{ssm_param_name}'を取得します。")
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print(f"エラー: パラメータ {ssm_param_name} の取得に失敗しました: {e}")
        raise


# --- グローバル変数の初期化 ---
# 外部APIの認証情報をSSMから取得
LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_ACCESS_TOKEN_PARAM_NAME)
api_url_token_pairs = []

print("情報: 運行情報APIのアクセストークンをSSMから読み込んでいます。")
for api_url in LINE_API_URL:
    if api_url == "https://api.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = ODPT_ACCESS_TOKEN_PARAM_NAME
    elif api_url == "https://api-challenge.odpt.org/api/v4/odpt:TrainInformation":
        PARAM_NAME = CHALLENGE_ACCESS_TOKEN_PARAM_NAME
    else:
        # 設定にないAPI URLが指定された場合はエラー
        print("エラー: 無効なAPI URLが設定されています。")
        raise ValueError("LINE_API_URLリストに無効なAPI URLが含まれています。")

    API_TOKEN = get_ssm_parameter(PARAM_NAME)
    api_url_token_pairs.append([api_url, API_TOKEN])
print("情報: APIトークンの読み込みが完了しました。")


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
    print(f"情報: S3オブジェクトを取得します。Bucket: '{bucket_name}', Key: '{key}'")
    try:
        response_s3flagfile = s3_client.get_object(Bucket=bucket_name, Key=key)
        file_content_string = response_s3flagfile["Body"].read().decode("utf-8")

        # ファイルが空かチェック
        if not file_content_string.strip():
            print(f"警告: S3ファイル'{key}'は空です。空のリストを返します。")
            return []

        s3_object_list = json.loads(file_content_string)

        # 内容がリスト形式かチェック
        if not isinstance(s3_object_list, list):
            print(
                f"警告: S3ファイル'{key}'はJSONリスト形式ではありません。空のリストを返します。"
            )
            return []

        print(
            f"情報: S3オブジェクト'{key}'から {len(s3_object_list)} 件の項目を読み込みました。"
        )
        return s3_object_list
    except ClientError as e:
        # オブジェクトが存在しない場合は正常なケースとしてNoneを返す
        if e.response["Error"]["Code"] == "NoSuchKey":
            print(f"情報: S3オブジェクト'{key}'が見つかりませんでした。")
            return None
        else:
            # その他のAWSエラーは例外を再送出
            print(f"エラー: S3へのアクセス中に予期せぬエラーが発生しました: {e}")
            raise


def get_line_list(s3_lineuserid_list):
    """複数のユーザーIDに基づき、DynamoDBから各ユーザーが設定した路線情報を取得する.

    Args:
        s3_lineuserid_list (list): 路線情報を取得したいLINEユーザーIDのリスト。

    Returns:
        list: 全ユーザーの路線情報を一意に集約したリスト。
    """
    if not s3_lineuserid_list:
        print("情報: ユーザーIDリストが空のため、DynamoDBのクエリをスキップします。")
        return []

    user_route_list = []
    print(
        f"情報: DynamoDBから {len(s3_lineuserid_list)} 人のユーザーの路線情報取得を開始します。"
    )

    for user_id in s3_lineuserid_list:
        try:
            print(f"情報: ユーザー'{user_id}'のデータをクエリしています...")
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
                print(
                    f"  -> ユーザー'{user_id}'の路線が {len(route_list)} 件見つかりました。"
                )
                user_route_list.extend(route_list)
            else:
                print(f"  -> ユーザー'{user_id}'の路線は見つかりませんでした。")

        except ClientError as e:
            print(
                f"エラー: ユーザー'{user_id}'のデータ取得に失敗しました: {e.response['Error']['Message']}"
            )
            continue  # エラーが発生したユーザーはスキップして処理を続行

    # 全ユーザーの路線リストから重複を排除
    unique_user_route_list = list(set(user_route_list))
    print(
        f"情報: 全ユーザーから合計 {len(unique_user_route_list)} 件のユニークな路線が見つかりました。"
    )
    print(f"デバッグ: ユニークな路線リスト: {unique_user_route_list}")

    return unique_user_route_list


def get_realtime_train_information():
    """リアルタイム運行情報APIを呼び出し、全路線の現在の運行状況を取得する.

    設定された複数のAPIエンドポイントから情報を収集し、結果を一つのリストに結合する。

    Returns:
        list | None: 全路線の運行情報のリスト。APIリクエストに失敗した場合はNone。
    """
    print("情報: 全てのAPIエンドポイントからリアルタイム運行情報を取得します...")
    try:
        realtime_data_list = []
        for url, token in api_url_token_pairs:
            print(f"情報: APIエンドポイントを呼び出します: {url}")
            params = {"acl:consumerKey": token}

            response = requests.get(url, params=params)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生させる

            response_data = response.json()
            realtime_data_list.extend(response_data)
            print(f"  -> {len(response_data)} 件のレコードを取得しました。")

        print(
            f"情報: 取得完了。合計 {len(realtime_data_list)} 件のレコードを取得しました。"
        )
        return realtime_data_list

    except requests.exceptions.RequestException as e:
        print(f"エラー: APIへのリクエストに失敗しました。\n{e}")
        return None


def create_snd_message(user_route, message):
    """遅延情報を示すLINE Flex MessageのJSONオブジェクトを生成する.

    Args:
        user_route (str): 路線名 (例: "JR山手線")。
        message (str): 運行情報の詳細テキスト。

    Returns:
        dict: LINE Flex MessageのJSONオブジェクト。
    """
    print(f"情報: 路線'{user_route}'のFlex Messageを作成します。")
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
    print(f"情報: ユーザー'{user_id}'にLINEメッセージを送信します...")

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

        print(
            f"情報: メッセージの送信に成功しました。ステータスコード: {response.status_code}"
        )
        return True

    except requests.exceptions.RequestException as e:
        print("エラー: LINEへのメッセージ送信に失敗しました。")
        if e.response is not None:
            print(f"  ステータスコード: {e.response.status_code}")
            print(f"  レスポンスボディ: {e.response.text}")
        else:
            print(f"  エラー詳細: {e}")
        return False


def delay_check(user_route_list, realtime_data_list, railway_list, s3_delay_list):
    # アクティブユーザーが設定した各路線について遅延をチェック
    new_delay_messages_list = []

    print(
        f"情報: アクティブユーザーの {len(user_route_list)} 件の路線の処理を開始します。"
    )
    for user_route in user_route_list:
        print(f"--- 路線'{user_route}'の処理を開始 ---")
        send_flg = True
        railway_name = None
        message = None
        # ユーザー設定の路線名 (例: "JR山手線") をAPIで使われる鉄道名 (例: "odpt.Railway:JR-East.Yamanote") に変換
        for route_railway in railway_list:
            if route_railway["route"] == user_route:
                railway_name = route_railway["odpt:railway"]
                break
        if not railway_name:
            print(
                f"  警告: '{user_route}'に一致する鉄道名が見つかりませんでした。スキップします。"
            )
            continue
        print(f"  -> 鉄道名'{railway_name}'にマッピングされました。")
        # 鉄道名に一致するリアルタイム運行情報を検索
        for realtime_data in realtime_data_list:
            if realtime_data["odpt:railway"] == railway_name:
                message = realtime_data["odpt:trainInformationText"]["ja"]
                break
        if not message:
            print(
                f"  警告: 鉄道名'{railway_name}'のリアルタイム情報が見つかりませんでした。スキップします。"
            )
            continue
        print(f"  -> 運行情報メッセージが見つかりました: '{message}'")
        # 取得した運行情報が「平常運転」など、通知不要なメッセージでないかチェック
        for delay_message in s3_delay_list:
            if delay_message["messages"] == message:
                send_flg = False
                print(
                    "  -> このメッセージは既知の通常運行メッセージです。通知は送信されません。"
                )
                break
        # 通知フラグがTrueの場合、通知処理を実行
        if send_flg:
            print(
                "  -> 新規の遅延またはステータス変更を検知しました。通知の準備をします。"
            )

            message_object = create_snd_message(user_route, message)

            # パーティションキーでユーザーの項目を全て取得
            response = user_table.query(
                IndexName="route-index",
                KeyConditionExpression=Key(ROUTE_COLUMN_NAME).eq(user_route),
            )

            user_list = [
                item[PRIMARY_USER_KEY_NAME] for item in response.get("Items", [])
            ]

            for user_id in user_list:
                snd_line_message(user_id, message_object)

            new_delay_message = {"route": user_route, "messages": message}
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
            print(
                "情報: フラグファイルにユーザーIDが見つかりませんでした。S3キャッシュの路線のみ使用します。"
            )
            user_route_list = []
        else:
            # 設定変更のあったユーザーの路線情報をDynamoDBから取得
            print(
                f"情報: {len(s3_lineuserid_list)} 件のユーザーIDを読み込みました。DynamoDBから路線情報を取得します。"
            )
            user_route_list = get_line_list(s3_lineuserid_list)

        # --- 2. 路線リストの統合とキャッシュ保存 ---
        # DynamoDBから取得したリストとS3キャッシュをマージし、最新の状態でS3に保存
        combined_route_list = list(set(user_route_list + s3_route_list))
        print(f"情報: 統合後のユニークな路線は {len(combined_route_list)} 件です。")
        route_string = json.dumps(combined_route_list, indent=2, ensure_ascii=False)
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME, Key=ROUTE_LIST_FILE_KEY, Body=route_string
        )
        print(
            f"情報: 統合後の路線リストをS3キャッシュ'{ROUTE_LIST_FILE_KEY}'に保存しました。"
        )

        # --- 3. リアルタイム運行情報の取得 ---
        realtime_data_list = get_realtime_train_information()
        if realtime_data_list is None:
            raise Exception("リアルタイム運行情報の取得に失敗しました。")

        # --- 4. マッピングと遅延判定の準備 ---
        # ローカルのJSONファイルから路線マッピングと無視するメッセージリストを読み込む
        with open(RAILWAY_LIST_FILE_NAME, "r", encoding="utf-8") as f:
            railway_list = json.load(f)
        print(f"情報: {len(railway_list)} 件の路線・鉄道マッピングを読み込みました。")

        # --- 5. 遅延判定と通知処理 ---
        delay_check(user_route_list, realtime_data_list, railway_list, s3_delay_list)

        print("== Lambdaハンドラの処理が正常に終了しました。 ==")
        return {
            "statusCode": 200,
            "body": json.dumps("Process finished successfully.", ensure_ascii=False),
        }
    except Exception as e:
        # ハンドラ全体で予期せぬエラーをキャッチし、ログに出力
        print(f"致命的エラー: lambda_handlerで予期せぬエラーが発生しました: {e}")
        return {"statusCode": 500, "body": json.dumps(str(e), ensure_ascii=False)}
