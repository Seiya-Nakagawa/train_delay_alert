resource "aws_lambda_function" "user_settings_lambda" {
  function_name = "${local.name_prefix}-lambda-user-settings"
  handler       = "user_settings_lambda.lambda_handler"
  runtime       = var.lambda_runtime_version
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
      USERS_TABLE_NAME          = aws_dynamodb_table.users.name
      LINE_CHANNEL_SECRET_NAME  = aws_ssm_parameter.line_channel_secret.name
      LINE_CHANNEL_ACCESS_TOKEN_NAME = aws_ssm_parameter.line_channel_access_token.name
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-user-settings-lambda"
  })
}

resource "aws_lambda_function_url" "user_settings_url" {
  function_name      = aws_lambda_function.user_settings_lambda.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function" "check_delay_lambda" {
  function_name = "${local.name_prefix}-lambda-check-delay"
  handler       = "check_delay_handler.lambda_handler"
  runtime       = var.lambda_runtime_version
  timeout       = var.lambda_timeout_seconds # タイムアウト（秒）
  memory_size   = var.lambda_memory_size     # メモリサイズ（MB）
  role          = aws_iam_role.lambda_exec_role.arn
  # archive_fileで動的にZIP化したファイルを、デプロイパッケージとして直接指定します
  filename         = data.archive_file.user_settings_lambda_function_zip.output_path
  source_code_hash = data.archive_file.user_settings_lambda_function_zip.output_base64sha256

  environment {
    variables = {
      USERS_TABLE_NAME        = aws_dynamodb_table.users.name
      TRAIN_STATUS_TABLE_NAME = aws_dynamodb_table.train_status.name
      TRAFFIC_API_TOKEN_NAME  = aws_ssm_parameter.traffic_api_token.name
      LINE_CHANNEL_ACCESS_TOKEN_NAME = aws_ssm_parameter.line_channel_access_token.name
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-check-delay"
  })
}