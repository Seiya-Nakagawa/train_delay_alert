# =============================================================================
# CloudWatch Alarms
# =============================================================================
# Lambda関数のエラーを監視し、閾値を超えた場合にSNSトピックへ通知するための
# CloudWatchアラームを定義します。

# -----------------------------------------------------------------------------
# Alarm for user_settings_lambda
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "user_settings_lambda_errors" {
  alarm_name          = "${local.name_prefix}-user-settings-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"          # 1評価期間で判断
  metric_name         = "Errors"     # 監視するメトリクス
  namespace           = "AWS/Lambda" # メトリクスの名前空間
  period              = "60"         # 評価期間（秒）
  statistic           = "Sum"        # 統計方法
  threshold           = "1"          # 閾値
  alarm_description   = "user_settings_lambdaでエラーが1回以上発生した場合にアラートを発報します。"
  actions_enabled     = true
  treat_missing_data  = "notBreaching"

  # アラームの対象となるLambda関数を指定
  dimensions = {
    FunctionName = aws_lambda_function.user_settings_lambda.function_name
  }

  # アラーム状態になった時に通知するSNSトピック
  alarm_actions = [aws_sns_topic.sns_topic_system.arn]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-user-settings-lambda-errors"
  })
}

# -----------------------------------------------------------------------------
# Alarm for check_delay_lambda
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "check_delay_lambda_errors" {
  alarm_name          = "${local.name_prefix}-check-delay-lambda-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "60"
  statistic           = "Sum"
  threshold           = "1"
  alarm_description   = "check_delay_lambdaでエラーが1回以上発生した場合にアラートを発報します。"
  actions_enabled     = true
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.check_delay_lambda.function_name
  }

  alarm_actions = [aws_sns_topic.sns_topic_system.arn]

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-check-delay-lambda-errors"
  })
}
