terraform {
  required_providers {
    netlify = {
      source  = "netlify/netlify"
      version = ">= 0.2.3"
    }
  }
}

variable "records" {
  description = "Netlify DNS records"
  type = list(object({
    zone   = string
    name   = string
    type   = string
    values = list(string)
    ttl    = optional(number)
  }))
  default = []
}

variable "netlify_team_slug" {
  description = "Optional Netlify team slug. If provided, zones will be created when missing."
  type        = string
  default     = ""
}

resource "netlify_dns_zone" "zone" {
  for_each  = var.netlify_team_slug == "" ? {} : { for z in distinct([for r in var.records : r.zone]) : z => z }
  name      = each.key
  team_slug = var.netlify_team_slug
}

data "netlify_dns_zone" "zone" {
  for_each = var.netlify_team_slug == "" ? { for z in distinct([for r in var.records : r.zone]) : z => z } : {}
  name     = each.key
}

locals {
  zone_id_by_name = merge(
    { for k, z in netlify_dns_zone.zone : k => z.id },
    { for k, z in data.netlify_dns_zone.zone : k => z.id }
  )
}

# Create records. Netlify requires one record per value; expand values.
resource "netlify_dns_record" "this" {
  for_each = {
    for rec in flatten([
      for r in var.records : [
        for v in r.values : {
          key      = "${r.zone}|${r.name}|${upper(r.type)}|${v}"
          zone_id  = lookup(local.zone_id_by_name, r.zone, null)
          hostname = r.name
          type     = upper(r.type)
          value    = v
          ttl      = try(r.ttl, null)
        }
      ]
    ]) : rec.key => rec
  }

  zone_id  = each.value.zone_id
  hostname = each.value.hostname
  type     = each.value.type
  value    = each.value.value

  # Note: TTL is not supported by all providers; Netlify API may ignore it.
  # Keep this attribute commented unless confirmed supported by provider version.
  # ttl = each.value.ttl
}

output "applied" {
  value = {
    count = length(netlify_dns_record.this)
    zones = distinct([for r in netlify_dns_record.this : r.zone_id])
  }
}


