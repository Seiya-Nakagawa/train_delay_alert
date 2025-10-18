variable "aws_region" {
  description = "デプロイするAWSリージョン"
  type        = string
}

variable "system_name" {
  description = "システム識別子"
  type        = string
}

variable "env" {
  description = "環境識別子"
  type        = string
}

variable "aws_account_id" {
  description = "AWSアカウントID"
  type        = string
}

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
  description = "Lambdaのログレベル"
  type        = string
}

variable "notification_emails" {
  description = "通知を受け取るメールアドレスのリスト"
  type        = list(string)
  default     = []
}

variable "frontend_redirect_url" {
  description = "フロントエンドのURL"
  type        = string
}

variable "frontend_origin" {
  description = "フロントエンドのオリジン"
  type        = string
}

variable "line_channel_id" {
  description = "LINEチャネルID"
  type        = string
}