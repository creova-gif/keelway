output "alb_dns_name" {
  description = "Public DNS name of the Keelway Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "control_plane_url" {
  description = "Base URL for Keelway Control Plane & Studio"
  value       = "http://${aws_lb.main.dns_name}"
}

output "worm_primary_bucket_name" {
  description = "Name of the Tier 2 S3 Object Lock Compliance WORM bucket"
  value       = aws_s3_bucket.worm_primary.id
}

output "worm_primary_bucket_arn" {
  description = "ARN of the Tier 2 S3 Object Lock Compliance WORM bucket"
  value       = aws_s3_bucket.worm_primary.arn
}

output "postgres_endpoint" {
  description = "Private endpoint for the encrypted RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.endpoint
}

output "kms_key_arn" {
  description = "ARN of the KMS Customer Managed Key"
  value       = aws_kms_key.keelway.arn
}
