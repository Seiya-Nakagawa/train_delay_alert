# =============================================================================
# Lambda
# =============================================================================
# アプリケーションのコアロジックを実行するLambda関数を定義します。

# -----------------------------------------------------------------------------
# Lambda Layer
# -----------------------------------------------------------------------------
# 複数のLambda関数で共有するライブラリ（requestsなど）をまとめたレイヤーを定義します。
# レイヤーを使用することで、各関数のデプロイパッケージサイズを削減できます。
resource "aws_lambda_layer_version" "dependencies_layer" {
  layer_name  = "${local.name_prefix}-python-libraries-layer"
  description = "Pythonの共通ライブラリ (requests, etc.)"

  s3_bucket = aws_s3_bucket.s3_train_alert.id
  s3_key    = aws_s3_object.lambda_layer_zip.key
  # レイヤーのソースコードのハッシュ値。この値が変更されると、新しいバージョンのレイヤーが作成されます。
  # archive_fileデータソースが生成したZIPファイルのハッシュ値を指定します。
  source_code_hash = data.archive_file.lambda_layer.output_base64sha256

  compatible_runtimes = var.lambda_runtime_version
}

# -----------------------------------------------------------------------------
# Lambda Function: user_settings_lambda
# -----------------------------------------------------------------------------
# ユーザー設定の取得・更新を行うLambda関数
resource "aws_lambda_function" "user_settings_lambda" {
  function_name = "${local.name_prefix}-lambda-user-settings"
  handler       = "user_settings_lambda.lambda_handler" # 実行するハンドラ
  runtime       = var.lambda_runtime_version[0]
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_size
  role          = aws_iam_role.lambda_exec_role.arn

  # デプロイパッケージの指定
  filename = data.archive_file.user_settings_lambda_function_zip.output_path
  source_code_hash = base64sha256(join("", [
    file("${path.module}/lambda/user_settings_lambda.py"),
    file("${path.module}/lambda/railway_list.json")
  ]))

  # 共通ライブラリレイヤーをアタッチ
  layers = [aws_lambda_layer_version.dependencies_layer.arn]

  # ログ設定
  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.user_settings_lambda_lg.name
  }

  # 環境変数
  environment {
    variables = {
      LINE_CHANNEL_ID                = var.line_login_channel_id
      LINE_CHANNEL_SECRET_PARAM_NAME = aws_ssm_parameter.line_channel_secret.name
      USER_TABLE_NAME                = aws_dynamodb_table.users.name
      FRONTEND_REDIRECT_URL          = var.frontend_redirect_url
      FRONTEND_ORIGIN                = var.frontend_origin
      S3_OUTPUT_BUCKET               = aws_s3_bucket.s3_train_alert.id
      SNS_TOPIC_ARN                  = aws_sns_topic.sns_topic_system.arn
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-user-settings-lambda"
  })
}

# Lambda Function URL: user_settings_lambdaへのHTTPSエンドポイント
resource "aws_lambda_function_url" "user_settings_url" {
  function_name      = aws_lambda_function.user_settings_lambda.function_name
  authorization_type = "NONE" # 認証はLambda関数内で独自に行う

  # CORS設定: 指定したオリジンからのPOSTリクエストを許可
  cors {
    allow_credentials = false
    allow_origins     = [var.frontend_origin]
    allow_methods     = ["*"]
    allow_headers     = ["Content-Type"]
    max_age           = 86400 # 1日
  }
}

# -----------------------------------------------------------------------------
# Lambda Function: check_delay_lambda
# -----------------------------------------------------------------------------
# 電車の遅延情報をチェックするLambda関数
resource "aws_lambda_function" "check_delay_lambda" {
  function_name = "${local.name_prefix}-lambda-check-delay"
  handler       = "check_delay_handler.lambda_handler"
  runtime       = var.lambda_runtime_version[0]
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_size
  role          = aws_iam_role.lambda_exec_role.arn

  # デプロイパッケージ
  filename = data.archive_file.check_delay_handler_function_zip.output_path
  source_code_hash = base64sha256(join("", [
    file("${path.module}/lambda/check_delay_handler.py"),
    file("${path.module}/lambda/railway_list.json")
  ]))

  layers = [aws_lambda_layer_version.dependencies_layer.arn]

  # 環境変数
  environment {
    variables = {
      LINE_CHANNEL_ID                   = var.line_post_channel_id
      LINE_ACCESS_TOKEN_PARAM_NAME      = aws_ssm_parameter.line_channel_access_token.name
      ODPT_ACCESS_TOKEN_PARAM_NAME      = aws_ssm_parameter.odpt_access_token.name
      CHALLENGE_ACCESS_TOKEN_PARAM_NAME = aws_ssm_parameter.challenge_access_token.name
      S3_OUTPUT_BUCKET                  = aws_s3_bucket.s3_train_alert.id
      TRAIN_STATUS_TABLE_NAME           = aws_dynamodb_table.train_status.name
      USER_TABLE_NAME                   = aws_dynamodb_table.users.name
      NG_WORD                           = var.ng_word[0]
      RESPONSE_TIMEOUT                  = var.response_timeout
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-check-delay"
  })
}
