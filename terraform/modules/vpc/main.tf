resource "aws_vpc" "vpc" {
cidr_block = var.vpc_cidr
}
resource "aws_internet_gateway" "igw" {
tags = {
Name = "igw"
}
}
resource "aws_subnet" "public_subnet" {
cidr_block = var.vpc_pubsubnet_cidr
vpc_id     = aws_vpc.vpc.id
tags = {
Name = "public_subnet"
}
}
resource "aws_subnet" "private_subnet" {
cidr_block = var.vpc_privsubnet_cidr
vpc_id     = aws_vpc.vpc.id
tags = {
Name = "private_subnet"
}
}
resource "aws_route_table" "public_rt" {
vpc_id = aws_vpc.vpc.id
tags = {
Name = "public_rt"
}
}
resource "aws_route_table" "private_rt" {
vpc_id = aws_vpc.vpc.id
tags = {
Name = "private_rt"
}
}
resource "aws_route" "igw_route" {
route_table_id = aws_route_table.public_rt.id
gateway_id     = aws_internet_gateway.igw.id
destination_cidr_block = "0.0.0.0/0"
}
resource "aws_route" "private_rt_route" {
route_table_id = aws_route_table.private_rt.id
gateway_id     = aws_internet_gateway.igw.id
destination_cidr_block = "0.0.0.0/0"
}
resource "aws_route_table_association" "public_subnet_assoc" {
route_table_id = aws_route_table.public_rt.id
subnet_id     = aws_subnet.public_subnet.id
}
resource "aws_route_table_association" "private_subnet_assoc" {
route_table_id = aws_route_table.private_rt.id
subnet_id     = aws_subnet.private_subnet.id
}