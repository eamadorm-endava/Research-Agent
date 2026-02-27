module "api_manager" {
  source           = "../modules/api-manager" # Path to your custom module
  project_services = var.project_services
}