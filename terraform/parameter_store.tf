# =============================================================================
# SSM Parameter Store
# =============================================================================
# LINEのチャネルシークレットなど、コードに直接記述したくない機密情報を
# AWS Systems Manager パラメータストアに保存します。

# -----------------------------------------------------------------------------
# LINE Channel Secret
# -----------------------------------------------------------------------------
resource "aws_ssm_parameter" "line_channel_secret" {
  # パラメータ名 (階層的に管理)
  name  = "/${local.name_prefix}/line/channel_secret"
  # SecureString型: KMSキーを使用して値を暗号化
  type  = "SecureString"
  # 初期値 (ダミー)
  value = "dummy-secret-value-to-be-changed-in-console"

  # ライフサイクル設定: コンソールで手動で値を変更した後に、
  # Terraformがこの初期値で上書きしないようにignore_changesを設定します。
  lifecycle {
    ignore_changes = [
      value,
    ]
  }

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/line/channel_secret"
  })
}

# -----------------------------------------------------------------------------
# LINE Channel Access Token
# -----------------------------------------------------------------------------
resource "aws_ssm_parameter" "line_channel_access_token" {
  name  = "/${local.name_prefix}/line/channel_access_token"
  type  = "SecureString"
  value = "dummy-access-token-to-be-changed-in-console"

  lifecycle {
    ignore_changes = [
      value,
    ]
  }

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/line/channel_access_token"
  })
}

# -----------------------------------------------------------------------------
# Traffic API Token (Example)
# -----------------------------------------------------------------------------
# 外部の交通情報APIを使用する場合のトークン格納例
resource "aws_ssm_parameter" "traffic_api_token" {
  name  = "/${local.name_prefix}/traffic/api_token"
  type  = "SecureString"
  value = "dummy-api-token-to-be-changed-in-console"

  lifecycle {
    ignore_changes = [
      value,
    ]
  }

  tags = merge(local.tags, {
    Name = "/${local.name_prefix}/traffic/api_token"
  })
}