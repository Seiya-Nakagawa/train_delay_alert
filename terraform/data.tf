# ----------------------------------------------------
# 関数コード用のZIPファイルを自動で作成するためのデータソース
# ----------------------------------------------------
data "archive_file" "user_settings_lambda_function_zip" {
  type        = "zip"
  
  # ZIPに含めるソースファイルを指定します (ワーキングディレクトリからの相対パス)
  source_file = "${path.module}/lambda/user_settings_lambda.py"
  
  # Terraformが実行される一時ディレクトリにZIPファイルが作成されます
  output_path = "${path.module}/build/user_settings_lambda_function.zip"
}

data "archive_file" "check_delay_handler_function_zip" {
  type        = "zip"
  
  # ZIPに含めるソースファイルを指定します (ワーキングディレクトリからの相対パス)
  source_file = "${path.module}/lambda/check_delay_handler.py"
  
  # Terraformが実行される一時ディレクトリにZIPファイルが作成されます
  output_path = "${path.module}/build/check_delay_handler_function.zip"
}