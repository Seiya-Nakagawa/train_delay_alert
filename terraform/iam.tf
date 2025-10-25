# =============================================================================
# IAM (Identity and Access Management)
# =============================================================================
# Lambda関数が他のAWSサービスにアクセスするためのロールとポリシーを定義します。

# -----------------------------------------------------------------------------
# IAM Role for Lambda
# -----------------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec_role" {
  # ロール名
  name = "${local.name_prefix}-lambda-exec-role"

  # 信頼ポリシー: Lambdaサービスがこのロールを引き受ける(AssumeRole)ことを許可
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [
      {
        Action    = "sts:AssumeRole",
        Effect    = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  # 共通タグ
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-exec-role"
  })
}

# -----------------------------------------------------------------------------
# IAM Policies for Lambda
# -----------------------------------------------------------------------------
# Lambda関数にアタッチする管理ポリシーを定義します。

# CloudWatch Logsへの書き込みを許可するポリシー
# これにより、Lambda関数はログを記録できます。
resource "aws_iam_role_policy_attachment" "lambda_policy_cwlogs" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDBへのフルアクセスを許可するポリシー
# ユーザー設定や遅延情報の読み書きに使用します。
resource "aws_iam_role_policy_attachment" "lambda_policy_dynamodb_fullaccess" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
}

# SSM Parameter Storeへの読み取り専用アクセスを許可するポリシー
# LINEのチャネルシークレットなどの機密情報を取得するために使用します。
resource "aws_iam_role_policy_attachment" "lambda_policy_ssm_readonly" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess"
}