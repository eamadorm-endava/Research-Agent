output "load_balancer_ip" {
  description = "The global IP address for the UI Frontend Load Balancer. Point your DNS records here."
  value       = google_compute_global_address.ui_frontend_ip.address
}
