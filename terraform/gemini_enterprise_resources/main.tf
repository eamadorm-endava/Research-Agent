data "google_project" "project" {
  project_id = var.project_id
}

module "enable_apis" {
  source = "../base_modules/api-manager"
  project_services = {
    (var.project_id) = var.services_to_enable
  }
}

resource "google_project_iam_member" "sa_ge_roles" {
  for_each = toset(var.ge_sa_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.sa_name}@${var.project_id}.iam.gserviceaccount.com"

  depends_on = [module.enable_apis]
}
