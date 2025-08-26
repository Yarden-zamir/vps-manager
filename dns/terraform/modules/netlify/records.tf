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

locals {
  prepared = [
    for r in var.records : {
      zone    = r.zone
      name    = r.name
      type    = upper(r.type)
      values  = r.values
      ttl     = try(r.ttl, null)
    }
  ]
}

# Create records. Netlify requires one record per value; expand values.
resource "netlify_dns_record" "this" {
  for_each = {
    for i, rec in flatten([
      for r in local.prepared : [
        for v in r.values : merge(r, {
          key    = "${r.zone}|${r.name}|${r.type}|${v}|${i}"
          value  = v
        })
      ]
    ]) : rec.key => rec
  }

  domain   = each.value.zone
  hostname = each.value.name
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


