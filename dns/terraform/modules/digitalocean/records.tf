terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = ">= 2.0.0"
    }
  }
}

variable "records" {
  description = "DigitalOcean DNS records"
  type = list(object({
    zone   = string
    name   = string
    type   = string
    values = list(string)
    ttl    = optional(number)
  }))
  default = []
}

# DO requires creating one resource per record; certain types support extra fields, but we'll use value mapping.
resource "digitalocean_record" "this" {
  for_each = {
    for rec in flatten([
      for r in var.records : [
        for v in r.values : {
          key   = "${r.zone}|${r.name}|${r.type}|${v}"
          zone  = r.zone
          name  = r.name
          type  = upper(r.type)
          value = v
          ttl   = try(r.ttl, null)
        }
      ]
    ]) : rec.key => rec
  }

  domain = each.value.zone
  type   = each.value.type
  name   = each.value.name
  value  = each.value.value
  ttl    = coalesce(try(each.value.ttl, null), 0)
}

output "applied" {
  value = {
    count = length(digitalocean_record.this)
    zones = distinct([for r in digitalocean_record.this : r.domain])
  }
}


