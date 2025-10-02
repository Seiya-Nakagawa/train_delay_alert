locals {
  name_prefix = "${var.system_name}-${var.env}"

  tags = {
    SystemName = var.system_name,
    Env        = var.env
  }
}
