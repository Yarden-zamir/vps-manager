terraform {
  required_providers {
    linode = {
      source  = "linode/linode"
      version = ">= 2.0.0"
    }
  }
}

variable "records" {
  description = "Linode DNS records"
  type = list(object({
    zone   = string
    name   = string
    type   = string
    values = list(string)
    ttl    = optional(number)
  }))
  default = []
}

data "linode_domains" "all" {}

locals {
  zone_name_to_id = { for d in data.linode_domains.all.domains : d.domain => d.id }
}

resource "linode_domain_record" "this" {
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

  domain_id = lookup(local.zone_name_to_id, each.value.zone)
  name      = each.value.name
  type      = each.value.type
  target    = each.value.value
  ttl_sec   = coalesce(try(each.value.ttl, null), 0)
}

output "applied" {
  value = {
    count = length(linode_domain_record.this)
    zones = distinct([for r in linode_domain_record.this : r.domain_id])
  }
}


