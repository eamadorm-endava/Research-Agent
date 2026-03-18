output "artifact_registry_id" {
  description = "Fully qualified Artifact Registry repository id."
  value       = module.artifact_registry.id
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL."
  value       = module.artifact_registry.url
}