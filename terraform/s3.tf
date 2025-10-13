resource "aws_s3_bucket" "s3_train_alert" {
  bucket = "${var.system_name}-${var.env}-s3"

  tags = {
    Name       = "${var.system_name}-${var.env}-s3",
    SystemName = var.system_name,
    Env        = var.env,
  }
}

## 暗号化
resource "aws_s3_bucket_server_side_encryption_configuration" "s3_encryption_train_alert" {
  bucket = aws_s3_bucket.s3_train_alert.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

## バージョニング設定
resource "aws_s3_bucket_versioning" "versioning_train_alert_results" {
  bucket = aws_s3_bucket.s3_train_alert.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "folders" {
  # for_eachに、上で定義したフォルダ名のセットを渡します
  for_each = local.s3_folder_names

  # フォルダを作成したいバケットのIDを指定
  bucket = aws_s3_bucket.s3_train_alert.id

  # each.keyには、"gas_url/"、"processed_files/"などのフォルダ名が順番に入ります
  key = each.key

  # フォルダであることを示すContent-Type
  content_type = "application/x-directory"

  # 中身は空
  content = ""

  # 空のコンテンツのMD5ハッシュ値を指定
  etag = md5("")
}

# 2. ローカルのZIPファイルをS3にアップロードするリソース
resource "aws_s3_object" "lambda_layer_zip" {
  # 依存関係: バケットが作成された後に実行される
  bucket = aws_s3_bucket.s3_train_alert.id
  key    = "lambda-layers/train_python_libraries.zip" # S3内でのファイルパス
  source = "${path.module}/lambda-layers/python_libraries.zip" # ローカルのZIPファイルのパス
  
  # ファイルの内容が変わった時だけ再アップロードするための設定
  etag = filemd5("${path.module}/lambda-layers/python_libraries.zip")
}

# ライフサイクルルール (最新3世代を保持)
resource "aws_s3_bucket_lifecycle_configuration" "lifecycle_train_alert" {
  # ライフサイクルルールはバージョニングが有効になっている必要があるため、depends_onを追加します
  depends_on = [aws_s3_bucket_versioning.versioning_train_alert_results]

  bucket = aws_s3_bucket.s3_train_alert.id

  rule {
    id     = "keep-last-3-versions"
    status = "Enabled"

    # バケット内のすべてのオブジェクトにルールを適用
    filter {}

    # 非現行（古い）バージョンのオブジェクトに対するアクション
    noncurrent_version_expiration {
      noncurrent_days = 1
      newer_noncurrent_versions = 2
    }
  }
}