terraform {
  backend "gcs" {
    # The bucket and prefix are injected by the CI/CD pipeline via -backend-config
    # bucket = "..."
    # prefix = "terraform/state/ui-frontend-resources"
  }
}
