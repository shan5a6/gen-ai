terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "dvsmcb52025-bkt1"
    key            = "terraform.tfstate"
    region         = "us-west-2"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "> 5.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
}
