locals {
  # Flatten the map into a list of objects for for_each
  service_pairs = flatten([
    for project, services in var.project_services : [
      for service in services : {
        project = project
        service = service
      }
    ]
  ])
}

resource "google_project_service" "project_services" {
  for_each = {
    for pair in local.service_pairs : "${pair.project}-${pair.service}" => pair
  }

  project                    = each.value.project
  service                    = each.value.service
  disable_on_destroy         = var.disable_on_destroy
  disable_dependent_services = var.disable_dependent_services
}