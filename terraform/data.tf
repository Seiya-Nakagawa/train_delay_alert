# =============================================================================
# Data Sources
# =============================================================================
# 既存のリソースや、Terraformの管理外で生成されるデータを参照するために使用します。
# ここでは、Lambda関数コードをZIPファイルにアーカイブするために使用しています。

# -----------------------------------------------------------------------------
# Archive for user_settings_lambda
# -----------------------------------------------------------------------------
# user_settings_lambda.py をZIP化します。
data "archive_file" "user_settings_lambda_function_zip" {
  type = "zip"
  
  # ZIPに含めるソースファイルを指定
  source_file = "${path.module}/lambda/user_settings_lambda.py"
  
  # 出力されるZIPファイルのパス
  output_path = "${path.module}/build/user_settings_lambda_function.zip"
}

# -----------------------------------------------------------------------------
# Archive for check_delay_handler
# -----------------------------------------------------------------------------
# check_delay_handler.py をZIP化します。
data "archive_file" "check_delay_handler_function_zip" {
  type = "zip"
  
  # ZIPに含めるソースファイルを指定
  source_file = "${path.module}/lambda/check_delay_handler.py"
  
  # 出力されるZIPファイルのパス
  output_path = "${path.module}/build/check_delay_handler_function.zip"
}