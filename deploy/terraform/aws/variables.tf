variable "aws_region" {
  description = "AWS region for Keelway infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "keelway"
}

variable "vpc_cidr" {
  description = "CIDR block for Keelway VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for multi-AZ high availability"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "worm_retention_days" {
  description = "Number of days for Tier 2 S3 Object Lock Compliance Mode retention"
  type        = number
  default     = 365
}

variable "db_instance_class" {
  description = "RDS PostgreSQL instance type"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  description = "Allocated storage in GB for PostgreSQL"
  type        = number
  default     = 20
}

variable "container_image" {
  description = "Keelway container image"
  type        = string
  default     = "ghcr.io/creova-gif/keelway:latest"
}

variable "control_plane_cpu" {
  description = "Fargate vCPU for control plane"
  type        = number
  default     = 512
}

variable "control_plane_memory" {
  description = "Fargate memory (MB) for control plane"
  type        = number
  default     = 1024
}

variable "runner_replica_count" {
  description = "Number of outbound isolated runner daemon instances"
  type        = number
  default     = 2
}
