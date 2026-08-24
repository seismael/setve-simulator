terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

# VPC & High-Throughput Subnet Provisioning
resource "aws_vpc" "steve_dev_vpc" {
  cidr_block           = "10.100.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "steve-${var.environment}-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "steve_dev_subnet" {
  vpc_id                  = aws_vpc.steve_dev_vpc.id
  cidr_block              = "10.100.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = {
    Name = "steve-${var.environment}-subnet"
  }
}

resource "aws_internet_gateway" "steve_gw" {
  vpc_id = aws_vpc.steve_dev_vpc.id
}

resource "aws_route_table" "steve_rt" {
  vpc_id = aws_vpc.steve_dev_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.steve_gw.id
  }
}

resource "aws_route_table_association" "steve_rta" {
  subnet_id      = aws_subnet.steve_dev_subnet.id
  route_table_id = aws_route_table.steve_rt.id
}

# Security Group for Ephemeral Bare-Metal Development Node
resource "aws_security_group" "steve_dev_sg" {
  name        = "steve-${var.environment}-sg"
  description = "Security group for STEVE kernel testing and dev node"
  vpc_id      = aws_vpc.steve_dev_vpc.id

  # SSH for developer access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # High-throughput internal worker traffic & gRPC barrier sync
  ingress {
    from_port   = 5000
    to_port     = 5050
    protocol    = "tcp"
    cidr_blocks = ["10.100.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Dedicated Metal Instance supporting Direct I/O, NUMA, and io_uring
resource "aws_instance" "steve_dev_node" {
  ami           = "ami-0c7217cdde317cfec" # Ubuntu 22.04 LTS (Kernel 5.15+)
  instance_type = "c6i.metal"             # Bare-metal non-virtualized instance for Direct I/O

  subnet_id                   = aws_subnet.steve_dev_subnet.id
  vpc_security_group_ids      = [aws_security_group.steve_dev_sg.id]
  associate_public_ip_address = true

  root_block_device {
    volume_size           = 200
    volume_type           = "gp3"
    iops                  = 10000
    throughput            = 1000
    delete_on_termination = true
  }

  user_data = file("${path.module}/scripts/user_data.sh")

  tags = {
    Name        = "steve-${var.environment}-baremetal-node"
    Environment = var.environment
    Role        = "developer-sandbox"
  }
}

output "dev_node_public_ip" {
  value       = aws_instance.steve_dev_node.public_ip
  description = "Public IP for SSH developer access to the ephemeral dev node"
}
