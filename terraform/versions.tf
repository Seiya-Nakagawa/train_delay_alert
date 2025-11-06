# =============================================================================
# Terraform & Provider Versions
# =============================================================================
# Terraformのバージョン、バックエンド(Terraform Cloud)、
# および使用するプロバイダー（AWS, Archive）を定義します。

terraform {
  # Terraformの実行に必要な最小バージョンを指定
  required_version = ">= 1.12.2"

  # Terraform Cloudをバックエンドとして設定
  cloud {
    organization = "aibdlnew1-organization"

    # このコードが属するワークスペースを指定
    workspaces {
      name = "aws-train-prd"
    }
  }

  # この構成で使用するプロバイダーを定義
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }

    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# =============================================================================
# Provider Configuration
# =============================================================================
# AWSプロバイダーのデフォルト設定を行います。

provider "aws" {
  # リソースを作成するデフォルトのリージョンを指定
  region = var.aws_region
}