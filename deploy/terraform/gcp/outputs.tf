output "control_plane_url" {
  description = "Public URL for Cloud Run Keelway Control Plane"
  value       = google_cloud_run_v2_service.control_plane.uri
}

output "worm_secondary_bucket_name" {
  description = "Tier 2 GCS Locked WORM Bucket"
  value       = google_storage_bucket.worm_secondary.name
}
