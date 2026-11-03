terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "random_id" "suffix" {
  byte_length = 4
}

# ==============================================================================
# Tier 2 Dual-WORM Secondary Leg: GCS Bucket with Locked Retention Policy
# ==============================================================================

resource "google_storage_bucket" "worm_secondary" {
  name          = "${var.app_name}-worm-secondary-${var.environment}-${random_id.suffix.hex}"
  location      = var.gcp_region
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  retention_policy {
    is_locked        = true # Hardware compliance retention
    retention_period = var.worm_retention_days * 86400
  }
}

# ==============================================================================
# Cloud Run Service (Serverless Control Plane)
# ==============================================================================

resource "google_service_account" "keelway_sa" {
  account_id   = "${var.app_name}-sa-${var.environment}"
  display_name = "Keelway Service Account"
}

resource "google_storage_bucket_iam_member" "worm_writer" {
  bucket = google_storage_bucket.worm_secondary.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.keelway_sa.email}"
}

resource "google_cloud_run_v2_service" "control_plane" {
  name     = "${var.app_name}-control-plane-${var.environment}"
  location = var.gcp_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.keelway_sa.email

    containers {
      image = var.container_image
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
      env {
        name  = "KEELWAY_ENV"
        value = var.environment
      }
      env {
        name  = "WORM_SECONDARY_GCS_BUCKET"
        value = google_storage_bucket.worm_secondary.name
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = google_cloud_run_v2_service.control_plane.project
  location = google_cloud_run_v2_service.control_plane.location
  name     = google_cloud_run_v2_service.control_plane.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
