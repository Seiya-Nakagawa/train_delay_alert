# =============================================================================
# DynamoDB
# =============================================================================
# アプリケーションのデータを格納するためのDynamoDBテーブルを定義します。

# -----------------------------------------------------------------------------
# Users Table (データモデル変更版)
# -----------------------------------------------------------------------------
# ユーザーの設定情報と登録路線を格納します。
# 1ユーザーが複数のアイテム（プロフィール用x1, 路線用xN）を持つデータモデルです。
#
# ⚠️ 注意: このスキーマ変更はテーブルの再作成を伴うため、既存のデータはすべて削除されます。
#
resource "aws_dynamodb_table" "users" {
  name         = "${local.name_prefix}-users"
  billing_mode = "PAY_PER_REQUEST" # リクエストごとの課金

  # 複合プライマリキー (Composite Primary Key) を設定
  # これにより、1人のユーザーが複数のアイテム（設定情報や路線情報）を持つことができます。
  hash_key  = "lineUserId"     # パーティションキー: ユーザーを一意に識別
  range_key = "settingOrRoute" # ソートキー: ユーザー内のアイテムを区別（例: "#PROFILE#" や "JR山手線"）

  # 誤削除防止
  deletion_protection_enabled = true

  # プライマリキーとGSIで使用する属性をすべて定義します
  attribute {
    name = "lineUserId"
    type = "S" # String
  }
  attribute {
    name = "settingOrRoute"
    type = "S" # String
  }

  # GSI (Global Secondary Index) の設定
  # 路線名(settingOrRoute)からユーザー(lineUserId)を逆引き検索するために使用します。
  # これにより、check_delay_lambdaが効率的に通知対象ユーザーを検索できます。
  global_secondary_index {
    name = "route-index" # 新しいインデックス名

    # GSIのキー構成 (プライマリキーの逆)
    hash_key  = "settingOrRoute"
    range_key = "lineUserId"

    # インデックスにはキー属性のみを含めることで、効率とコストを最適化します。
    projection_type = "KEYS_ONLY"
  }

  # TTL (Time To Live) の設定
  # 有効期限が切れたアイテムを自動的に削除します。
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  # サーバーサイド暗号化を有効化
  server_side_encryption {
    enabled = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-users"
  })
}

# -----------------------------------------------------------------------------
# Train Status Table
# -----------------------------------------------------------------------------
# 路線の運行状況（遅延情報など）を一時的にキャッシュします。
# Yahoo路線情報へのアクセスを最小限に抑える目的で使用します。
resource "aws_dynamodb_table" "train_status" {
  name         = "${local.name_prefix}-train-status"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "routeId" # パーティションキー (路線の一意なID)

  # 誤削除防止
  deletion_protection_enabled = true

  attribute {
    name = "routeId"
    type = "S"
  }

  # TTL設定
  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  # サーバーサイド暗号化
  server_side_encryption {
    enabled = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-train-status"
  })
}
