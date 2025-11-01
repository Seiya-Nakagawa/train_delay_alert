# =============================================================================
# Variables
# =============================================================================
# このTerraform構成で使用される変数を定義します。
# tfvarsファイルや環境変数から値を注入できます。

# -----------------------------------------------------------------------------
# AWS General
# -----------------------------------------------------------------------------
variable "aws_region" {
  description = "デプロイするAWSリージョン"
  type        = string
}

variable "aws_account_id" {
  description = "AWSアカウントID"
  type        = string
}

# -----------------------------------------------------------------------------
# Project General
# -----------------------------------------------------------------------------
variable "system_name" {
  description = "システム識別子 (例: train-delay-alert)"
  type        = string
}

variable "env" {
  description = "環境識別子 (例: prd, stg, dev)"
  type        = string
}

# -----------------------------------------------------------------------------
# Lambda
# -----------------------------------------------------------------------------
variable "lambda_runtime_version" {
  description = "Lambdaランタイムのバージョン"
  type        = list(string)
}

variable "lambda_timeout_seconds" {
  description = "Lambdaのタイムアウト（秒）"
  type        = number
}

variable "lambda_memory_size" {
  description = "Lambdaのメモリサイズ（MB）"
  type        = number
}

variable "lambda_log_level" {
  description = "Lambdaのログレベル (未使用)"
  type        = string
}

variable "ng_word" {
  description = "NGワードのリスト"
  type        = list(string)
}

# -----------------------------------------------------------------------------
# Notification
# -----------------------------------------------------------------------------
variable "notification_emails" {
  description = "システムアラート通知を受け取るメールアドレスのリスト"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Frontend & LINE
# -----------------------------------------------------------------------------
variable "frontend_redirect_url" {
  description = "LINEログイン後にリダイレクトされるフロントエンドのURL"
  type        = string
}

variable "frontend_origin" {
  description = "CORS許可対象となるフロントエンドのオリジン"
  type        = string
}

variable "line_login_channel_id" {
  description = "LINEログインチャネルID"
  type        = string
}

variable "line_post_channel_id" {
  description = "LINE投稿チャネルID"
  type        = string
}
