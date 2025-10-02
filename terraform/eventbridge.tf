resource "aws_cloudwatch_event_rule" "check_delay_rule" {
  name                = "${local.name_prefix}-check-delay-rule"
  description         = "Trigger train delay check every 5 minutes"
  schedule_expression = "rate(5 minutes)"

  // TODO: 開発期間中は無効にしておく
  is_enabled = false

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-check-delay-rule"
  })
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.check_delay_rule.name
  target_id = "${local.name_prefix}-check-delay-lambda"
  arn       = aws_lambda_function.check_delay_lambda.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.check_delay_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.check_delay_rule.arn
}