#!/usr/bin/env bash
set -euo pipefail

echo "===================================================================="
echo "  ☁️ KEELWAY ENTERPRISE INFRASTRUCTURE: AWS PROVISIONING"
echo "===================================================================="

TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform/aws" && pwd)"
cd "$TF_DIR"

if ! command -v terraform &> /dev/null; then
    echo "[-] Error: terraform is not installed or not in PATH."
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo "[-] Error: aws CLI is not installed or not in PATH."
    exit 1
fi

echo "[+] 1. Initializing Terraform AWS provider and modules..."
terraform init

echo "[+] 2. Validating Terraform configuration syntax..."
terraform validate

echo "[+] 3. Creating deployment execution plan..."
terraform plan -out=tfplan

echo ""
echo "===================================================================="
echo "  Ready to deploy Keelway AWS Infrastructure:"
echo "  • VPC & Private Multi-AZ Subnets"
echo "  • Tier 2 S3 Object Lock Compliance WORM Bucket (365-day lock)"
echo "  • KMS Customer Managed Key"
echo "  • Private Encrypted PostgreSQL RDS Instance"
echo "  • ECS Fargate Cluster & Control Plane Services"
echo "  • Application Load Balancer with Health Checks"
echo "===================================================================="
read -p "Do you want to apply this plan now? (y/N): " -r CONFIRM
if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    terraform apply tfplan
    echo ""
    echo "===================================================================="
    echo "  ✓ AWS INFRASTRUCTURE PROVISIONED SUCCESSFULLY!"
    echo "===================================================================="
    terraform output
else
    echo "[!] Deployment aborted by user."
    rm -f tfplan
    exit 0
fi
