resource "aws_cloudwatch_log_group" "user_settings_lambda_lg" {
  name              = "/aws/lambda/${local.name_prefix}-lambda-user-settings"
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-user-settings"
  })
}

resource "aws_cloudwatch_log_group" "check_delay_lambda_lg" {
  name              = "/aws/lambda/${local.name_prefix}-lambda-check-delay"
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-check-delay"
  })
}
