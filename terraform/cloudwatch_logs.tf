resource "aws_cloudwatch_log_group" "user_settings_lambda_lg" {
  name              = "/aws/lambda/${aws_lambda_function.user_settings_lambda.function_name}"
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = aws_lambda_function.user_settings_lambda.function_name
  })
}

resource "aws_cloudwatch_log_group" "check_delay_lambda_lg" {
  name              = "/aws/lambda/${aws_lambda_function.check_delay_lambda.function_name}"
  retention_in_days = 1

  tags = merge(local.tags, {
    Name = aws_lambda_function.check_delay_lambda.function_name
  })
}
