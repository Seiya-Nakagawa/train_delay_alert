# =============================================================================
# S3 (Simple Storage Service)
# =============================================================================
# LambdaレイヤーのZIPファイルなどを保管するためのS3バケットを定義します。

# -----------------------------------------------------------------------------
# S3 Bucket
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "s3_train_alert" {
  # バケット名 (グローバルで一意である必要があります)
  bucket = "${var.system_name}-${var.env}-s3"

  tags = {
    Name       = "${var.system_name}-${var.env}-s3",
    SystemName = var.system_name,
    Env        = var.env,
  }
}

# -----------------------------------------------------------------------------
# S3 Bucket Configuration
# -----------------------------------------------------------------------------

# サーバーサイド暗号化 (SSE-S3) を有効化
resource "aws_s3_bucket_server_side_encryption_configuration" "s3_encryption_train_alert" {
  bucket = aws_s3_bucket.s3_train_alert.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# バージョニングを有効化
# オブジェクトの変更履歴を保持します。
resource "aws_s3_bucket_versioning" "versioning_train_alert_results" {
  bucket = aws_s3_bucket.s3_train_alert.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ライフサイクルルール (最新3世代以外の古いバージョンを削除)
resource "aws_s3_bucket_lifecycle_configuration" "lifecycle_train_alert" {
  # バージョニングが有効化された後にこのリソースが作成されるように依存関係を設定
  depends_on = [aws_s3_bucket_versioning.versioning_train_alert_results]

  bucket = aws_s3_bucket.s3_train_alert.id

  rule {
    id     = "keep-last-3-versions"
    status = "Enabled"

    # バケット内のすべてのオブジェクトにルールを適用
    filter {}

    # 非現行（古い）バージョンのオブジェクトに対するアクション
    noncurrent_version_expiration {
      noncurrent_days           = 1 # 1日経過した非現行バージョンを対象
      newer_noncurrent_versions = 2 # 最新の非現行バージョンを2つ保持
    }
  }
}

# -----------------------------------------------------------------------------
# S3 Objects
# -----------------------------------------------------------------------------

# S3バケット内にフォルダを作成
# resource "aws_s3_object" "folders" {
#   # local.s3_folder_namesの各要素に対してリソースを作成
#   for_each = local.s3_folder_names

#   bucket = aws_s3_bucket.s3_train_alert.id

#   # キーの末尾に "/" をつけることでフォルダとして扱われる
#   key = each.key

#   # フォルダであることを示すContent-Type
#   content_type = "application/x-directory"

#   # 空のコンテンツのMD5ハッシュ値を指定
#   etag = md5("")
# }

# LambdaレイヤーのZIPファイルをS3にアップロード
# resource "aws_s3_object" "lambda_layer_zip" {
#   bucket = aws_s3_bucket.s3_train_alert.id
#   key    = "lambda-layers/python_libraries.zip" # S3内でのオブジェクトキー
#   source = data.archive_file.lambda_layer.output_path
#   etag   = data.archive_file.lambda_layer.output_md5
# }
