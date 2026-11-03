# 🚀 Keelway Infrastructure & Deployment Guide

This directory contains production Infrastructure-as-Code (IaC), container orchestration, and Kubernetes manifests to provision and run Keelway across local, cloud, and hybrid environments.

---

## 📁 Directory Structure

```text
deploy/
├── scripts/
│   ├── deploy-local.sh              # One-click Docker Compose launcher with health checks
│   └── deploy-aws.sh                # Terraform automated AWS provisioning script
├── terraform/
│   ├── aws/                         # AWS ECS Fargate, RDS PostgreSQL, S3 Object Lock, KMS
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── gcp/                         # GCP Cloud Run & Tier 2 GCS Bucket Lock (Retention Policy)
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── k8s/                             # Production Kubernetes manifests
    ├── namespace.yaml               # Dedicated 'keelway' namespace
    ├── configmap.yaml               # Cluster configuration
    ├── networkpolicy.yaml           # Air-gap & least-privilege egress fencing
    ├── deployment-control-plane.yaml# Non-root (UID 10001) hardened control plane
    ├── deployment-runner.yaml       # Outbound customer runner daemon
    ├── service.yaml                 # Internal ClusterIP service
    └── ingress.yaml                 # TLS ingress with WebSocket proxy support
```

---

## 1. 💻 One-Click Local Infrastructure (Docker Compose)

To launch the complete containerized stack locally (Control Plane, Outbound Runner Daemon, and local Ollama model server):

```bash
./deploy/scripts/deploy-local.sh
```

Or manually:
```bash
docker compose up -d --build
```

**Services Launched:**
- **Keelway Control Plane & Studio Web IDE:** `http://localhost:8000`
- **Interactive REST API Documentation:** `http://localhost:8000/docs`
- **Local Ollama Model Server:** `http://localhost:11434`
- **Outbound Isolated Runner Daemon:** Container `keelway-runner` (zero ingress ports open)

---

## 2. ☁️ AWS Enterprise Cloud Infrastructure (Terraform)

Provisions the complete Tier 2 Hardware-Attested cloud footprint:
- **VPC & Subnets:** Isolated multi-AZ private subnets with NAT Gateway.
- **Tier 2 S3 Object Lock Compliance Mode Bucket:** WORM storage locked for 365 days (anti-tamper / anti-deletion invariant).
- **KMS Customer Managed Key:** Envelope encryption for audit trails and RDS storage.
- **Encrypted RDS PostgreSQL:** Private database cluster with automated snapshots.
- **ECS Fargate Cluster:** High-availability serverless containers running the control plane and runner daemon.
- **Application Load Balancer:** Health-checked TLS termination.

```bash
./deploy/scripts/deploy-aws.sh
```

Or step-by-step:
```bash
cd deploy/terraform/aws
terraform init
terraform plan
terraform apply
```

---

## 3. 🌐 GCP Secondary WORM Leg (Terraform)

Provisions the second leg of the **Tier 2 Dual-WORM Invariant (ADR-076)** on Google Cloud:
- **GCS Bucket Lock:** Locked bucket retention policy with hardware legal hold.
- **Cloud Run Service:** Scalable serverless Keelway control plane.

```bash
cd deploy/terraform/gcp
terraform init
terraform apply -var="gcp_project_id=YOUR_PROJECT_ID"
```

---

## 4. ☸️ Enterprise Kubernetes Deployment

To deploy Keelway into an existing Kubernetes cluster (EKS, GKE, AKS, or on-prem):

```bash
# 1. Create namespace, config, and network policies
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/networkpolicy.yaml

# 2. Deploy hardened Control Plane and Outbound Runner
kubectl apply -f deploy/k8s/deployment-control-plane.yaml
kubectl apply -f deploy/k8s/deployment-runner.yaml

# 3. Expose via Service and Ingress
kubectl apply -f deploy/k8s/service.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

**Security Invariants Enforced in Kubernetes:**
- `runAsNonRoot: true` (UID 10001, GID 10001).
- `allowPrivilegeEscalation: false`.
- All Linux capabilities dropped (`capabilities: drop: [ALL]`).
- Network policies deny incoming traffic to the runner daemon (outbound-only polling).
