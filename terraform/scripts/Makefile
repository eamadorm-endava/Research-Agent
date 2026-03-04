# --- Bootstrap Configuration ---
#PROJECT_ID             := p-dev-gce-60pf
SA_NAME                := terraform-sa-gemini-project
SA_EMAIL               := $(SA_NAME)@$(PROJECT_ID).iam.gserviceaccount.com
DEVELOPER_GROUP_EMAIL  := research-agent-dev-test@endava.com
REPO_NAME              := Research-Agent
REPO_OWNER             := eamadorm-endava

# Project Roles for the SA
ROLES := roles/serviceusage.serviceUsageAdmin \
         roles/iam.serviceAccountAdmin \
         roles/resourcemanager.projectIamAdmin

.PHONY: all bootstrap create-sa assign-roles grant-impersonation enable-apis create-triggers help

## bootstrap: Run the full initialization process
bootstrap: create-sa assign-roles grant-impersonation enable-apis create-triggers
	@echo "Bootstrap complete!"
	@echo "To use locally: gcloud auth application-default login --impersonate-service-account=$(SA_EMAIL)"

## create-sa: Create the Terraform Service Account
create-sa:
	@echo "Creating Service Account..."
	@if ! gcloud iam service-accounts describe $(SA_EMAIL) --project=$(PROJECT_ID) > /dev/null 2>&1; then \
		gcloud iam service-accounts create $(SA_NAME) \
			--display-name="Terraform Management Account" \
			--project=$(PROJECT_ID); \
	else \
		echo "Service Account $(SA_NAME) already exists."; \
	fi

## assign-roles: Assign IAM roles to the Service Account
assign-roles:
	@echo "Assigning infrastructure roles..."
	@$(foreach role,$(ROLES), \
		gcloud projects add-iam-policy-binding $(PROJECT_ID) \
			--member="serviceAccount:$(SA_EMAIL)" \
			--role="$(role)" \
			--condition=None; \
	)


## grant-impersonation: Grant token creation roles to devs and Cloud Build
grant-impersonation:
	@echo "Granting impersonation rights..."
	@# Developer Group
	@gcloud iam service-accounts add-iam-policy-binding $(SA_EMAIL) \
		--member="group:$(DEVELOPER_GROUP_EMAIL)" \
		--role="roles/iam.serviceAccountTokenCreator" \
		--project=$(PROJECT_ID)
	@# Cloud Build SA
	@$(eval PROJECT_NUMBER=$(shell gcloud projects describe $(PROJECT_ID) --format='value(projectNumber)'))
	@gcloud iam service-accounts add-iam-policy-binding $(SA_EMAIL) \
		--member="serviceAccount:$(PROJECT_NUMBER)@cloudbuild.gserviceaccount.com" \
		--role="roles/iam.serviceAccountTokenCreator" \
		--project=$(PROJECT_ID)

## enable-apis: Enable necessary Google Cloud APIs
enable-apis:
	@echo "Enabling Cloud Build API..."
	@gcloud services enable cloudbuild.googleapis.com --project=$(PROJECT_ID)

## create-triggers: Setup Cloud Build triggers for CI/CD
create-triggers:
	@echo "Creating Cloud Build Triggers..."
	@# API Services - CI
	@gcloud beta builds triggers create github --name="api-services-plan" --project="$(PROJECT_ID)" --repo-name="$(REPO_NAME)" --repo-owner="$(REPO_OWNER)" --pull-request-pattern="^main$$" --comment-control="COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY" --build-config="terraform/api-service/api-service-cloud-build-ci.yaml" --included-files="terraform/api-service/**"
	@# API Services - CD
	@gcloud beta builds triggers create github --name="api-services-apply" --project="$(PROJECT_ID)" --repo-name="$(REPO_NAME)" --repo-owner="$(REPO_OWNER)" --branch-pattern="^main$$" --build-config="terraform/api-service/api-service-cloud-build-cd.yaml" --included-files="terraform/api-service/**"
	@# Service Accounts - CI
	@gcloud beta builds triggers create github --name="service-accounts-plan" --project="$(PROJECT_ID)" --repo-name="$(REPO_NAME)" --repo-owner="$(REPO_OWNER)" --pull-request-pattern="^main$$" --comment-control="COMMENTS_ENABLED_FOR_EXTERNAL_CONTRIBUTORS_ONLY" --build-config="terraform/service-accounts/service-accounts-cloud-build-ci.yaml" --included-files="terraform/service-accounts/**"
	@# Service Accounts - CD
	@gcloud beta builds triggers create github --name="service-accounts-apply" --project="$(PROJECT_ID)" --repo-name="$(REPO_NAME)" --repo-owner="$(REPO_OWNER)" --branch-pattern="^main$$" --build-config="terraform/service-accounts/service-accounts-cloud-build-cd.yaml" --included-files="terraform/service-accounts/**"


## clean: This Step Deletes the Service Account and all Cloud Build Triggers## clean: This Step Deletes the Service Account and all Cloud Build Triggers
clean: 
	@echo "WARNING: This will delete $(SA_NAME) and all project triggers."
	@echo "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@echo "Deleting Cloud Build Triggers..."
	-gcloud beta builds triggers delete api-services-plan --project=$(PROJECT_ID) --quiet
	-gcloud beta builds triggers delete api-services-apply --project=$(PROJECT_ID) --quiet
	-gcloud beta builds triggers delete service-accounts-plan --project=$(PROJECT_ID) --quiet
	-gcloud beta builds triggers delete service-accounts-apply --project=$(PROJECT_ID) --quiet
	@echo "Deleting Service Account..."
	-gcloud iam service-accounts delete $(SA_EMAIL) --project=$(PROJECT_ID) --quiet
	@echo "Cleanup complete."