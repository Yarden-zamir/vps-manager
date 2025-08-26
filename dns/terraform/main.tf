terraform {
  required_version = ">= 1.5.0"
  required_providers {
    netlify = {
      source  = "netlify/netlify"
      version = ">= 1.0.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = ">= 4.0.0"
    }
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = ">= 2.0.0"
    }
    linode = {
      source  = "linode/linode"
      version = ">= 2.0.0"
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

provider "cloudflare" {
  api_token = var.dns_provider_token
}

provider "digitalocean" {
  token = var.dns_provider_token
}

provider "linode" {
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
  cloudflare_records   = var.records
  digitalocean_records = var.records
  linode_records       = var.records
}

module "netlify" {
  count  = local.selected_provider == "netlify" ? 1 : 0
  source = "./modules/netlify"

  records = local.netlify_records
}

module "cloudflare" {
  count  = local.selected_provider == "cloudflare" ? 1 : 0
  source = "./modules/cloudflare"

  records = local.cloudflare_records
}

module "digitalocean" {
  count  = local.selected_provider == "digitalocean" ? 1 : 0
  source = "./modules/digitalocean"

  records = local.digitalocean_records
}

module "linode" {
  count  = local.selected_provider == "linode" ? 1 : 0
  source = "./modules/linode"

  records = local.linode_records
}

variable "dns_provider_token" {
  description = "Generic DNS provider token (used for Netlify token)"
  type        = string
  sensitive   = true
}



