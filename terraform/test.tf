resource "aws_s3_bucket" "s3_train_alert_test" {
  # バケット名 (グローバルで一意である必要があります)
  bucket = "${var.system_name}-${var.env}-s3_test"

  tags = {
    Name       = "${var.system_name}-${var.env}-s3_test",
    SystemName = var.system_name,
    Env        = var.env,
  }
}
