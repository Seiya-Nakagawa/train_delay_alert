# =============================================================================
# CloudWatch Logs
# =============================================================================
# Lambda関数のログを保存するためのCloudWatch Log Groupを定義します。

# -----------------------------------------------------------------------------
# Log Group for user_settings_lambda
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "user_settings_lambda_lg" {
  # ロググループ名 (Lambdaの標準形式に合わせる)
  name              = "/aws/lambda/${local.name_prefix}-lambda-user-settings"
  # ログの保持期間 (日)
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-user-settings"
  })
}

# -----------------------------------------------------------------------------
# Log Group for check_delay_lambda
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "check_delay_lambda_lg" {
  name              = "/aws/lambda/${local.name_prefix}-lambda-check-delay"
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-check-delay"
  })
}