output "cloud_run_url" {
  description = "The URL of the Cloud Run service."
  value       = module.ekb_pipeline_cloud_run.service_uri
}

output "service_account_email" {
  description = "The email of the service account used by the EKB pipeline."
  value       = module.ekb-pipeline-service-account.email
}
