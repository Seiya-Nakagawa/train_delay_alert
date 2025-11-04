# =============================================================================
# EventBridge (CloudWatch Events)
# =============================================================================
# check_delay_lambda関数を定期的に実行するためのトリガーを定義します。

# -----------------------------------------------------------------------------
# Event Rule
# -----------------------------------------------------------------------------
# 5分ごとにイベントを発生させるルール
resource "aws_cloudwatch_event_rule" "check_delay_rule" {
  name        = "${local.name_prefix}-check-delay-rule"
  description = "5分ごとに電車の遅延情報をチェックするLambdaをトリガーします。"
  # スケジュール式 (rate式: 指定した間隔で実行)
  schedule_expression = "rate(60 minutes)"

  state = "ENABLED"

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-check-delay-rule"
  })
}

# -----------------------------------------------------------------------------
# Event Target
# -----------------------------------------------------------------------------
# イベントのターゲットとしてcheck_delay_lambda関数を指定
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.check_delay_rule.name
  target_id = "${local.name_prefix}-check-delay-lambda"
  arn       = aws_lambda_function.check_delay_lambda.arn
}

# -----------------------------------------------------------------------------
# Lambda Permission
# -----------------------------------------------------------------------------
# EventBridgeがcheck_delay_lambda関数を呼び出すことを許可
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.check_delay_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.check_delay_rule.arn
}
