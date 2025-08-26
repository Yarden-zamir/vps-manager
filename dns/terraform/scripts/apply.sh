#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v terraform >/dev/null 2>&1; then
  echo "Terraform not found. Install from https://developer.hashicorp.com/terraform/downloads" >&2
  exit 1
fi

terraform init -upgrade
terraform plan -out=tf.plan
terraform apply -auto-approve tf.plan



