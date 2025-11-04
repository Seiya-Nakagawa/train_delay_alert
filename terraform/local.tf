# =============================================================================
# Local Variables
# =============================================================================
# このTerraformモジュール内で使用するローカル変数を定義します。
# 繰り返し使用する値や、複雑な式に名前を付けるために使用します。

locals {
  # 共通のプレフィックスを定義
  name_prefix = "${var.system_name}-${var.env}"

  # 共通のタグを定義
  tags = {
    SystemName = var.system_name
    Env        = var.env
  }

  # S3に作成するフォルダ名のリスト
  s3_folder_names = toset([
    "lambda-layers/",
    "train-status-logs/"
  ])
}
