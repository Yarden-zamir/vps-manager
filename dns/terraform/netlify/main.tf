terraform {
  required_version = ">= 1.5.0"
  required_providers {
    netlify = {
      source  = "netlify/netlify"
      version = ">= 0.2.3"
    }
  }
  backend "local" {}
}

provider "netlify" {
  token = var.dns_provider_token
}

module "netlify" {
  source  = "../modules/netlify"
  records = var.records
}

variable "dns_provider_token" {
  description = "Generic DNS provider token"
  type        = string
  sensitive   = true
}

