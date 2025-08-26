terraform {
  required_version = ">= 1.5.0"
  required_providers {
    netlify = {
      source  = "netlify/netlify"
      version = ">= 0.2.3"
    }
  }
  backend "local" {
    path = "./terraform.tfstate"
  }
}

provider "netlify" {
  # Use explicit token from Terraform var to allow generic CI secret naming
  token = var.dns_provider_token
}

variable "dns_provider" {
  description = "DNS provider to target (netlify | cloudflare | digitalocean | linode)"
  type        = string
}

locals {
  # The same records schema is used for all providers
  selected_provider = lower(var.dns_provider)
  netlify_records   = var.records
}

module "netlify" {
  count  = local.selected_provider == "netlify" ? 1 : 0
  source = "./modules/netlify"

  records = local.netlify_records
}



variable "dns_provider_token" {
  description = "Generic DNS provider token (used for Netlify token)"
  type        = string
  sensitive   = true
}



