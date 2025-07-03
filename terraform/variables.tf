variable "vpc_cidr" {
type = string
default = "10.10.0.0/16"
}
variable "vpc_pubsubnet_cidr" {
type = string
default = "10.10.10.0/24"
}
variable "vpc_privsubnet_cidr" {
type = string
default = "10.10.20.0/24"
}
variable "region" {
type = string
default = "us-west-2"
}