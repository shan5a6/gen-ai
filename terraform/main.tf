module "vpc" {
source = "./modules/vpc"
vpc_cidr = var.vpc_cidr
vpc_pubsubnet_cidr = var.vpc_pubsubnet_cidr
vpc_privsubnet_cidr = var.vpc_privsubnet_cidr
}