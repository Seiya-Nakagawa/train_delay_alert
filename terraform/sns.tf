resource "aws_sns_topic" "sns_topic_system" {
  name         = "${local.name_prefix}-error-topic"
  display_name = "${local.name_prefix}-error-topic"

  delivery_policy = jsonencode({
    "http" : {
      "defaultHealthyRetryPolicy" : {
        "minDelayTarget"     : 20,
        "maxDelayTarget"     : 20,
        "numRetries"         : 3,
        "numMaxDelayRetries" : 0,
        "numNoDelayRetries"  : 0,
        "numMinDelayRetries" : 0,
        "backoffFunction"    : "linear"
      },
      "disableSubscriptionOverrides" : false,
      "defaultThrottlePolicy" : {
        "maxReceivesPerSecond" : 1
      }
    }
  })

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-error-topic"
  })
}

resource "aws_sns_topic_subscription" "email_target" {
  for_each = toset(var.notification_emails)

  topic_arn = aws_sns_topic.sns_topic_system.arn
  protocol  = "email"
  endpoint  = each.value
}