# =============================================================================
# DynamoDB
# =============================================================================
# アプリケーションのデータを格納するためのDynamoDBテーブルを定義します。

# -----------------------------------------------------------------------------
# Users Table
# -----------------------------------------------------------------------------
# ユーザーの設定情報（LINEユーザーID、登録路線、通知設定など）を格納します。
resource "aws_dynamodb_table" "users" {
  name         = "${local.name_prefix}-users"
  billing_mode = "PAY_PER_REQUEST" # リクエストごとの課金
  hash_key     = "lineUserId"      # パーティションキー

  # 誤削除防止
  deletion_protection_enabled = true

  # 属性の定義
  attribute {
    name = "lineUserId"
    type = "S" # String
  }

  attribute {
    name = "routes"
    type = "S"
  }


  # GSI (Global Secondary Index) の設定
  global_secondary_index {
    name            = "routesIndex"
    hash_key        = "routes"
    projection_type = "ALL" # 全ての属性をインデックスにプロジェクションする
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
