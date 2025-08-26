variable "records" {
  description = "List of DNS records to manage"
  type = list(object({
    zone     = string
    name     = string
    type     = string
    values   = list(string)
    ttl      = optional(number)
  }))
  default = []
}

output "applied_records" {
  value = {
    netlify     = try(module.netlify[0].applied, null)
    cloudflare  = try(module.cloudflare[0].applied, null)
    digitalocean= try(module.digitalocean[0].applied, null)
    linode      = try(module.linode[0].applied, null)
  }
}


