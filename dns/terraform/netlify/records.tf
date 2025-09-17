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
  value = module.netlify.applied
}


