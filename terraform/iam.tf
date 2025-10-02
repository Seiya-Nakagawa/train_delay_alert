resource "aws_iam_role" "lambda_exec_role" {
  name = "${local.name_prefix}-lambda-exec-role"

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

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-lambda-exec-role"
  })
}

# IAM Policy for Lambda (CloudWatch Logs)
resource "aws_iam_role_policy_attachment" "lambda_policy_cwlogs" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
# IAM Policy for Lambda (DynamoDB Full Access)
resource "aws_iam_role_policy_attachment" "lambda_policy_dynamodb_fullaccess" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
}