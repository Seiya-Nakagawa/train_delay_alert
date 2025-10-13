locals {
  name_prefix = "${var.system_name}-${var.env}"

  # ここに作成したいフォルダ名を追加・削除するだけでOK
  s3_folder_names = toset([
    "lambda-layers/"
  ])

  tags = {
    SystemName = var.system_name,
    Env        = var.env
  }
}