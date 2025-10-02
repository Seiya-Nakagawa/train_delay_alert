resource "aws_ssm_parameter" "line_channel_secret" {
  name  = "/${local.name_prefix}/line/channel_secret"
  type  = "SecureString"
  value = "dummy-secret"

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/line/channel_secret"
  })
}

resource "aws_ssm_parameter" "line_channel_access_token" {
  name  = "/${local.name_prefix}/line/channel_access_token"
  type  = "SecureString"
  value = "dummy-access-token"

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/line/channel_access_token"
  })
}

resource "aws_ssm_parameter" "traffic_api_token" {
  name  = "/${local.name_prefix}/traffic/api_token"
  type  = "SecureString"
  value = "dummy-api-token"

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/traffic/api_token"
  })
}