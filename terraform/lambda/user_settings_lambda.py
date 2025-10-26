# -*- coding: utf-8 -*-
"""ユーザー設定を管理するLambdaハンドラ.

フロントエンドからのリクエストを受け、LINEの認証、ユーザー情報の取得・更新を行います。
Lambda Function URLとCORS設定を介して、Webブラウザから直接呼び出されることを想定しています。

主な機能:
- LINEの認可コードを検証し、LINEユーザーIDを取得します。
- DynamoDBからユーザーの設定情報（路線、通知時間など）を取得します。
- DynamoDBにユーザーの設定情報を保存・更新します。
"""

import json
import os
from datetime import timedelta, timezone

import boto3
import requests
from botocore.exceptions import ClientError

# --- グローバル変数・初期設定 ---

# 環境変数から設定値を取得
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME = os.environ.get(
    "LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME"
)
LINE_CHANNEL_SECRET_PARAM_NAME = os.environ.get("LINE_CHANNEL_SECRET_PARAM_NAME")
USER_TABLE_NAME = os.environ.get("USER_TABLE_NAME")
FRONTEND_REDIRECT_URL = os.environ.get("FRONTEND_REDIRECT_URL")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")  # CORSで使用

# LINE APIのエンドポイント
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"

# タイムゾーン設定 (JST)
TIMEZONE = timezone(timedelta(hours=+9), "JST")

# AWSサービスクライアントの初期化
ssm_client = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(USER_TABLE_NAME)


# --- ヘルパー関数 ---


def get_ssm_parameter(ssm_param_name):
    """SSMパラメータストアから指定されたパラメータの値を取得します。

    Args:
        ssm_param_name (str): 取得するパラメータの名前。

    Returns:
        str: パラメータの値。

    Raises:
        ClientError: パラメータの取得に失敗した場合。
    """
    try:
        response = ssm_client.get_parameter(Name=ssm_param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        print(f"Error getting parameter {ssm_param_name}: {e}")
        raise


# 起動時にLINEチャネルシークレットを取得
LINE_CHANNEL_SECRET = get_ssm_parameter(LINE_CHANNEL_SECRET_PARAM_NAME)


def get_line_user_id(body):
    """LINEの認可コードを使用して、LINEユーザーIDを取得します。

    Args:
        body (dict): Lambdaに渡されたリクエストボディ。
                     'authorizationCode'キーを含む必要があります。

    Returns:
        str: 取得したLINEユーザーID。

    Raises:
        ValueError: 認可コードやIDトークンが取得できない場合。
        requests.exceptions.RequestException: LINE APIへのリクエストに失敗した場合。
    """
    auth_code = body.get("authorizationCode")
    if not auth_code:
        raise ValueError("認可コードが必要です。")

    # 1. 認可コードを使い、アクセストークンとIDトークンを取得
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
    response.raise_for_status()  # HTTPエラーがあれば例外を発生

    response_json = response.json()
    id_token = response_json.get("id_token")
    if not id_token:
        print(f"ERROR: IDトークンの抽出に失敗しました。Response: {response_json}")
        raise ValueError("IDトークンの抽出に失敗しました。")

    # 2. IDトークンを検証し、ユーザーID("sub")を取得
    verify_response = requests.post(
        LINE_VERIFY_URL,
        data={"id_token": id_token, "client_id": LINE_CHANNEL_ID},
    )
    verify_response.raise_for_status()

    verify_json = verify_response.json()
    line_user_id = verify_json.get("sub")
    if not line_user_id:
        print(f"ERROR: LINEユーザIDの取得に失敗しました。Response: {verify_json}")
        raise ValueError("LINEユーザIDの取得に失敗しました。")

    return line_user_id


def get_user_data(line_user_id):
    """DynamoDBからユーザーデータを取得します。

    Args:
        line_user_id (str): 取得するユーザーのLINE ID。

    Returns:
        dict or None: ユーザーデータが見つかった場合はその内容を辞書で返す。
                      見つからなかった場合はNoneを返す。

    Raises:
        ClientError: DynamoDBからのデータ取得に失敗した場合。
    """
    try:
        response = table.get_item(Key={"lineUserId": line_user_id})
        return response.get("Item")
    except ClientError as e:
        print(f"DynamoDBからのユーザーデータ取得でエラーが発生しました: {e}")
        raise


def post_user_data(user_data):
    """DynamoDBにユーザーデータを保存または更新します。

    Args:
        user_data (dict): 保存するユーザーデータの辞書。

    Raises:
        ClientError: DynamoDBへのデータ保存に失敗した場合。
    """
    try:
        table.put_item(Item=user_data)
    except ClientError as e:
        print(f"DynamoDBへのユーザーデータ登録でエラーが発生しました: {e}")
        raise


# --- メインハンドラ ---


def lambda_handler(event, context):
    """Lambda関数のメインエントリポイント。

    CORS設定済みのLambda Function URLを介して呼び出されることを想定しています。
    リクエストボディの内容に応じて、処理を振り分けます。

    - 'authorizationCode' が存在する場合: ユーザー情報の取得（初回アクセス）
    - 'lineUserId' が存在する場合: ユーザー情報（設定）の保存・更新

    Args:
        event (dict): Lambdaプロキシ統合からのイベントオブジェクト。
        context (object): Lambdaのランタイム情報を提供するオブジェクト。

    Returns:
        dict: API Gatewayプロキシ統合形式のレスポンスオブジェクト。
    """
    # CORSヘッダーをすべてのレスポンスに含める
    headers = {
        "Access-Control-Allow-Origin": FRONTEND_ORIGIN,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    # OPTIONSメソッドはCORSのプリフライトリクエスト。ヘッダーのみを返す。
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 204, "headers": headers}

    try:
        body = json.loads(event.get("body", "{}"))
        print(f"Received event: {json.dumps(body)}")

        # --- 処理の振り分け ---

        # 1. LINEログイン後の初回アクセス（認可コードが含まれる）
        if "authorizationCode" in body:
            try:
                print("LINEユーザーIDの取得を開始します。")
                line_user_id = get_line_user_id(body)
                print(f"LINEユーザーIDの取得に成功しました: {line_user_id}")
            except Exception as e:
                print(f"CRITICAL: get_line_user_idでエラーが発生しました: {e}")
                raise

            try:
                print(f"{line_user_id} のユーザーデータをDynamoDBから取得します。")
                user_data = get_user_data(line_user_id)
                print("DynamoDBからのデータ取得が完了しました。")
            except Exception as e:
                print(f"CRITICAL: get_user_dataでエラーが発生しました: {e}")
                raise

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
                "headers": headers,
                "body": json.dumps(user_data, ensure_ascii=False, default=str),
            }

        # 2. ユーザーによる設定情報の保存・更新（ユーザーIDが含まれる）
        elif "lineUserId" in body:
            # フロントエンドから送られてくる路線情報が { key: '...', name: '...' } のような
            # オブジェクトの配列である場合、後方互換性のために路線名だけの配列に変換する
            if (
                "routes" in body
                and body["routes"]
                and isinstance(body["routes"][0], dict)
            ):
                print(
                    "古い形式の路線データ（オブジェクト配列）を検出しました。文字列配列に変換します。"
                )
                body["routes"] = [
                    route["line_name"]
                    for route in body["routes"]
                    if "line_name" in route
                ]

            post_user_data(body)
            print(f"ユーザー情報を更新しました: {body.get('lineUserId')}")

            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps(body, ensure_ascii=False, default=str),
            }

        # 3. 上記以外の不正なリクエスト
        else:
            error_message = "不正なリクエストです。'authorizationCode'または'lineUserId'が含まれていません。"
            print(f"ERROR: {error_message}")
            return {
                "statusCode": 400,  # Bad Request
                "headers": headers,
                "body": json.dumps({"message": error_message}),
            }

    # 予期せぬエラー処理
    except Exception as e:
        print(f"ERROR: 予期せぬエラーが発生しました: {e}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps(
                {"message": f"サーバー内部でエラーが発生しました: {str(e)}"}
            ),
        }
