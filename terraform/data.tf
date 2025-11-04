# =============================================================================
# Data Sources
# =============================================================================
# 既存のリソースや、Terraformの管理外で生成されるデータを参照するために使用します。
# ここでは、Lambda関数コードをZIPファイルにアーカイブするために使用しています。

# -----------------------------------------------------------------------------
# Archive for Dummy Lambda Layer
# -----------------------------------------------------------------------------
# data "archive_file" "lambda_layer" {
#   type        = "zip"
#   source_dir  = "${path.module}/lambda-layers/dummy"
#   output_path = "${path.module}/build/dummy_layer.zip"
# }

# -----------------------------------------------------------------------------
# Archive for Dummy Lambda Function
# -----------------------------------------------------------------------------
# data "archive_file" "dummy_function_zip" {
#   type        = "zip"
#   source_file = "${path.module}/lambda/dummy_handler.py"
#   output_path = "${path.module}/build/dummy_function.zip"
# }
