resource "aws_cloudwatch_metric_alarm" "user_settings_lambda_errors" {
  alarm_name          = "${local.name_prefix}-user-settings-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Alarm when user_settings_lambda has errors"
  actions_enabled     = false

  dimensions = {
    FunctionName = aws_lambda_function.user_settings_lambda.function_name
  }

  alarm_actions = [aws_sns_topic.sns_topic_system.arn]
  ok_actions      = [aws_sns_topic.sns_topic_system.arn]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-user-settings-lambda-errors"
  })
}

resource "aws_cloudwatch_metric_alarm" "check_delay_lambda_errors" {
  alarm_name          = "${local.name_prefix}-check-delay-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "Alarm when check_delay_lambda has errors"
  actions_enabled     = false

  dimensions = {
    FunctionName = aws_lambda_function.check_delay_lambda.function_name
  }

  alarm_actions = [aws_sns_topic.sns_topic_system.arn]
  ok_actions      = [aws_sns_topic.sns_topic_system.arn]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-check-delay-lambda-errors"
  })
}