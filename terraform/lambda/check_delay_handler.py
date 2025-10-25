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

# --- 設定項目 (ご自身の環境に合わせて変更してください) ---
S3_BUCKET_NAME = "your-s3-bucket-name"  # S3バケット名
FLAG_FILE_KEY = "flags/update-required.flag"  # フラグファイルのS3キー
CACHE_FILE_KEY = "cache/train-lines.json"  # 路線リストキャッシュのS3キー
DYNAMODB_TABLE_NAME = "Users"  # ユーザーテーブル名
# GSIを利用して路線で検索する場合のインデックス名 (GSIを使わない場合はNone)
# GSIのパーティションキーが路線名であることを想定
LINE_GSI_NAME = "Line-gsi"
# ユーザーテーブルで路線情報が格納されているカラム名
LINE_COLUMN_NAME = "registeredLine"
# ----------------------------------------------------


def lambda_handler(event, context):
    """Lambda関数のメインハンドラ.

    Args:
        event (dict): Lambdaイベントデータ
        context (object): Lambdaランタイム情報

    Returns:
        dict: HTTPレスポンス
    """
    ## S3の路線リスト更新フラグファイルチェック

    return {"statusCode": 200, "body": json.dumps("Hello from check_delay_handler!")}
