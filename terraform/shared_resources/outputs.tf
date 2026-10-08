output "artifact_registry_id" {
  description = "Fully qualified Artifact Registry repository id."
  value       = module.artifact_registry.id
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL."
  value       = module.artifact_registry.url
}
output "embedding_model_config" {
  description = "Arguments for the Cloud SDK model creation step."
  value = {
    project_id    = var.project_id
    region        = var.main_region
    dataset_id    = var.bq_dataset_id
    connection_id = var.bq_vertex_connection_id
  }
}
