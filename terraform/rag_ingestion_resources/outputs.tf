output "cloud_function_uri" {
  description = "The URI of the deployed Cloud Function"
  value       = module.rag_function.uri
}

output "bq_connection_id" {
  description = "The BigQuery connection ID"
  value       = google_bigquery_connection.vertex_ext.name
}
