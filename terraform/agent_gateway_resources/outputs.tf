output "forwarding_rule_ip" {
  description = "The internal IP address of the Regional Internal Application Load Balancer"
  value       = google_compute_forwarding_rule.mcp_forwarding_rule.ip_address
}

output "gateway_dns_name" {
  description = "The fully-qualified domain name of the MCP Gateway"
  value       = "gateway.${var.dns_domain_name}"
}

output "url_map_id" {
  description = "The ID of the Regional URL Map"
  value       = google_compute_region_url_map.mcp_url_map.id
}

output "network_attachment_id" {
  description = "The ID of the Compute Engine Network Attachment for Vertex AI Agent Engine"
  value       = google_compute_network_attachment.agent_network_attachment.id
}
