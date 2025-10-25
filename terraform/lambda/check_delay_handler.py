# -*- coding: utf-8 -*-
"""遅延情報をチェックするLambdaハンドラ.

EventBridgeからの定期的なトリガーを受け取り、対象の路線情報をYahoo路線情報から取得します。
遅延が発生している場合は、SNSにメッセージを発行してユーザーに通知します。

TODO:
    - DynamoDBから全ユーザーの設定を取得するロジックの実装
    - 現在時刻とユーザー設定（通知時間帯、曜日）を比較するロジックの実装
    - 対象路線の遅延情報をYahoo路線情報からスクレイピングする機能の実装
    - 遅延発生時にSNSトピックへ通知メッセージを発行する機能の実装
"""

import json
import os

import boto3
from botocore.exceptions import ClientError

# --- 設定項目 (ご自身の環境に合わせて変更してください) ---
S3_BUCKET_NAME = os.environ.get("S3_OUTPUT_BUCKET")
FLAG_FILE_KEY = "update-required.flag"  # フラグファイルのS3キー
CACHE_FILE_KEY = "train-list.json"  # 路線リストキャッシュのS3キー
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
# DynamoDBのGSI名
ROUTE_GSI_NAME = "Line-gsi"
# ユーザーテーブルで路線情報が格納されているカラム名
ROUTE_COLUMN_NAME = "routes"
# ----------------------------------------------------

# Boto3クライアントの初期化 (ハンドラ外で定義すると再利用され効率的)
s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
user_table = dynamodb.Table(USER_TABLE_NAME)


def check_flag_file():
    """フラグファイルの存在確認

    Args:
        なし

    Returns:
        str: true or false

    Raises:
        ClientError: パラメータの取得に失敗した場合。
    フラグファイルの存在確認結果。

    Raises:
        ClientError: パラメータの取得に失敗した場合。
    """
    try:
        # 1. フラグファイルの存在確認
        s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=FLAG_FILE_KEY)

        # head_objectが成功 = ファイルが存在する
        return True

    except ClientError as e:
        # head_objectでファイルが存在しない場合、404エラーが返る
        if e.response["Error"]["Code"] == "404":
            print("フラグファイルは見つかりませんでした。S3のキャッシュを利用します。")
            return False
        else:
            # その他のS3関連エラー
            print(f"S3アクセス中に予期せぬエラーが発生しました: {e}")
            raise e


def get_line_list():
    unique_lines = set()
    scan_kwargs = {"ProjectionExpression": ROUTE_COLUMN_NAME}

    while True:
        response_line_list = user_table.scan(**scan_kwargs)
        print("--- DynamoDBからの生のレスポンス ---")
        print(response_line_list)


def lambda_handler(event, context):
    """Lambda関数のメインハンドラ.

    Args:
        event (dict): Lambdaイベントデータ
        context (object): Lambdaランタイム情報

    Returns:
        dict: HTTPレスポンス
    """

    # 路線情報の確認
    if check_flag_file():
        print("フラグファイルが見つかりました。DynamoDBに路線情報を確認します。")

        try:
            line_list = get_line_list()
            return line_list
        except ClientError as e:
            print(f"DynamoDBからのユーザーデータ取得でエラーが発生しました: {e}")
            raise

    else:
        print("フラグファイルが見つかりませんでした。S3のキャッシュを利用します。")

    return {"statusCode": 200, "body": json.dumps("Hello from check_delay_handler!")}
