# Terraformの実行環境に関する設定
terraform {
  required_version = ">= 1.12.2"

  # Terraform Cloudをバックエンドとして設定
  cloud {
    organization = "aibdlnew1-organization"

    # このコードがどのワークスペース群に属するかを示すタグを設定
    workspaces {
      name = "aws-train-prd"
    }
  }

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

# プライマリリージョン (東京)
provider "aws" {
  region = "ap-northeast-1"
}
