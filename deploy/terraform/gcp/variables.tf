variable "gcp_project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "keelway"
}

variable "worm_retention_days" {
  description = "Retention period in days for GCS Bucket Lock"
  type        = number
  default     = 365
}

variable "container_image" {
  description = "Keelway container image"
  type        = string
  default     = "gcr.io/creova-gif/kora:latest"
}
