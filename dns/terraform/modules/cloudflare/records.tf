terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = ">= 4.0.0"
    }
  }
}

variable "records" {
  description = "Cloudflare DNS records"
  type = list(object({
    zone   = string
    name   = string
    type   = string
    values = list(string)
    ttl    = optional(number)
  }))
  default = []
}

data "cloudflare_zone" "this" {
  for_each = { for z in distinct([for r in var.records : r.zone]) : z => z }
  name     = each.key
}

resource "cloudflare_record" "this" {
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

  zone_id = data.cloudflare_zone.this[each.value.zone].id
  name    = each.value.name == "" ? "@" : each.value.name
  type    = each.value.type
  value   = each.value.value
  ttl     = coalesce(try(each.value.ttl, null), 1)
}

output "applied" {
  value = {
    count = length(cloudflare_record.this)
    zones = distinct([for r in cloudflare_record.this : r.zone_id])
  }
}


