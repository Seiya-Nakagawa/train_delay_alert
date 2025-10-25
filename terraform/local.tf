# =============================================================================
# Local Variables
# =============================================================================
# このTerraformモジュール内で使用するローカル変数を定義します。
# 繰り返し使用する値や、複雑な式に名前を付けるために使用します。

locals {
  # リソース名などに付与する共通のプレフィックス (例: train-delay-alert-prd)
  name_prefix = "${var.system_name}-${var.env}"

  # S3バケットに作成するフォルダ名のリスト
  s3_folder_names = toset([
    "lambda-layers/",
  ])

  # LambdaレイヤーとしてアップロードするZIPファイルのローカルパス
  lambda_layer_zip_path = "${path.module}/lambda-layers/python_libraries.zip"

  # すべてのリソースに付与する共通のタグ
  tags = {
    SystemName = var.system_name,
    Env        = var.env
  }
}
