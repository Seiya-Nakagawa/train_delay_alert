# ----------------------------------------------------
# Lambdaレイヤーを定義
# ライブラリ(dependencies.zip)は、手動でS3にアップロードされていることを前提とします。
# ----------------------------------------------------
resource "aws_lambda_layer_version" "dependencies_layer" {
  layer_name          = "${var.system_name}-${var.env}-laver-python-libraries"
  description         = "Shared libraries for link checker"
  s3_bucket           = aws_s3_bucket.s3_train_alert.id
  s3_key              = aws_s3_object.lambda_layer_zip.key
  s3_object_version   = aws_s3_object.lambda_layer_zip.version_id
  # S3上のZIPが更新されたことを検知するために、そのファイルのETag(ハッシュ値)を監視します
  # source_code_hash    = aws_s3_object.lambda_layer_zip.etag
  compatible_runtimes = var.lambda_runtime_version
}

resource "aws_lambda_function" "user_settings_lambda" {
  function_name = "${local.name_prefix}-lambda-user-settings"
  handler       = "user_settings_lambda.lambda_handler"
  runtime       = var.lambda_runtime_version[0]
  timeout       = var.lambda_timeout_seconds # タイムアウト（秒）
  memory_size   = var.lambda_memory_size     # メモリサイズ（MB）
  role          = aws_iam_role.lambda_exec_role.arn
  # archive_fileで動的にZIP化したファイルを、デプロイパッケージとして直接指定します
  filename         = data.archive_file.user_settings_lambda_function_zip.output_path
  source_code_hash = data.archive_file.user_settings_lambda_function_zip.output_base64sha256

  layers = [aws_lambda_layer_version.dependencies_layer.arn]

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "INFO"
    log_group             = aws_cloudwatch_log_group.user_settings_lambda_lg.name
  }

  environment {
    variables = {
      USERS_TABLE_NAME                      = aws_dynamodb_table.users.name
      USERS_TABLE_NAME                      = aws_dynamodb_table.users.name
      LINE_CHANNEL_ID                       = var.line_channel_id
      LINE_CHANNEL_ACCESS_TOKEN_PARAM_NAME  = aws_ssm_parameter.line_channel_access_token.name
      LINE_CHANNEL_SECRET_PARAM_NAME        = aws_ssm_parameter.line_channel_secret.name
      TABLE_NAME                            = aws_dynamodb_table.users.name
      FRONTEND_URL                          = var.frontend_url
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-user-settings-lambda"
  })
}

resource "aws_lambda_function_url" "user_settings_url" {
  function_name      = aws_lambda_function.user_settings_lambda.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = [var.frontend_url]
    allow_methods     = ["POST", "OPTIONS"]
    allow_headers     = ["Content-Type"]
    expose_headers    = []
    max_age           = 86400 # 1日
  }
}

resource "aws_lambda_function" "check_delay_lambda" {
  function_name = "${local.name_prefix}-lambda-check-delay"
  handler       = "check_delay_handler.lambda_handler"
  runtime       = var.lambda_runtime_version[0]
  timeout       = var.lambda_timeout_seconds # タイムアウト（秒）
  memory_size   = var.lambda_memory_size     # メモリサイズ（MB）
  role          = aws_iam_role.lambda_exec_role.arn
  # archive_fileで動的にZIP化したファイルを、デプロイパッケージとして直接指定します
  filename         = data.archive_file.check_delay_handler_function_zip.output_path
  source_code_hash = data.archive_file.check_delay_handler_function_zip.output_base64sha256

  layers = [aws_lambda_layer_version.dependencies_layer.arn]

  environment {
    variables = {
      USERS_TABLE_NAME        = aws_dynamodb_table.users.name
      TRAIN_STATUS_TABLE_NAME = aws_dynamodb_table.train_status.name
      TRAFFIC_API_TOKEN_NAME  = aws_ssm_parameter.traffic_api_token.name
      LINE_CHANNEL_ACCESS_TOKEN_NAME = aws_ssm_parameter.line_channel_access_token.name
      TABLE_NAME                      = aws_dynamodb_table.train_status.name
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-check-delay"
  })
}