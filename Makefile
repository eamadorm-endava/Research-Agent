PROJECT_ID?=host-ge-prod-endava-01-yd8e# ?= is used to set a default value if the variable is not set in the .env file
REGION?=europe-west2
BIGQUERY_PROD_URL?=https://bigquery-mcp-server-1057005221381.europe-west2.run.app
DRIVE_PROD_URL?=https://drive-mcp-server-1057005221381.europe-west2.run.app
GCS_PROD_URL?=https://gcs-mcp-server-1057005221381.europe-west2.run.app
CALENDAR_PROD_URL?=https://calendar-mcp-server-1057005221381.europe-west2.run.app
EKB_PIPELINE_URL?=https://ekb-pipeline-1057005221381.europe-west2.run.app
GOOGLE_AUTH_ID?=mock-GE-drive-auth-resource-id
LANDING_ZONE_BUCKET?=$(PROJECT_ID)-ai-agent-landing-zone
METRICS_DATASET_ID?=agent_metrics
METRICS_TABLE_ID?=response_times
### General Commands ###

gcloud-auth:
	gcloud config unset auth/impersonate_service_account
	gcloud auth application-default login --project=$(PROJECT_ID)
	gcloud config set project $(PROJECT_ID)

gcloud-auth-terraform:
	gcloud auth application-default login --project=$(PROJECT_ID) --impersonate-service-account=terraform-sa-gemini-project@$(PROJECT_ID).iam.gserviceaccount.com
	gcloud config set auth/impersonate_service_account terraform-sa-gemini-project@$(PROJECT_ID).iam.gserviceaccount.com

install-precommit:
	uvx pre-commit install

run-precommit:
	uvx pre-commit run --all-files

verify-all-ci:
	$(MAKE) verify-agent-ci
	$(MAKE) verify-bq-ci
	$(MAKE) verify-gcs-ci
	$(MAKE) verify-drive-ci
	$(MAKE) verify-calendar-ci
	$(MAKE) verify-metrics-ci
	$(MAKE) verify-onedrive-ci
	$(MAKE) verify-sharepoint-ci
	$(MAKE) verify-ekb-ci
	$(MAKE) verify-atlassian-ci

create-cloudbuild-triggers:
	./terraform/scripts/cicd_triggers_creation.sh

bootstrap:
	./terraform/scripts/bootstrap.sh

bootstrap-no-shared:
	APPLY_SHARED_RESOURCES=false ./terraform/scripts/bootstrap.sh

### AI Agent Commands ###

run-agent-precommit:
	uvx pre-commit run --files agent/**/*

test-agent:
	cd agent && uv run --group ai-agent --group dev pytest tests/ -v

run-ui-agent:
	cd agent && \
	uv run --group ai-agent adk web --port 8000 --artifact_service_uri gs://$(LANDING_ZONE_BUCKET)

deploy-agent:
	uv export \
		--group ai-agent \
		--no-hashes \
		--no-annotate \
		-o agent/core_agent/requirements.txt
	uv run --group ai-agent --group dev python -m agent.deployment.deploy \
		--project ${PROJECT_ID} \
		--location ${REGION} \
		--display-name "test-ai-agent" \
		--source-packages=./agent \
		--entrypoint-module=agent.core_agent.agent \
		--entrypoint-object=app \
		--requirements-file=./agent/core_agent/requirements.txt \
		--service-account=adk-agent@${PROJECT_ID}.iam.gserviceaccount.com \
		--set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},MODEL_ARMOR_TEMPLATE_ID=security-template,BIGQUERY_URL=${BIGQUERY_PROD_URL},DRIVE_URL=${DRIVE_PROD_URL},GCS_URL=${GCS_PROD_URL},CALENDAR_URL=${CALENDAR_PROD_URL},GEMINI_GOOGLE_AUTH_ID=${GOOGLE_AUTH_ID},EKB_PIPELINE_URL=${EKB_PIPELINE_URL},LANDING_ZONE_BUCKET=${LANDING_ZONE_BUCKET},METRICS_PROJECT_ID=${PROJECT_ID},METRICS_DATASET_ID=${METRICS_DATASET_ID},METRICS_TABLE_ID=${METRICS_TABLE_ID}"
	rm agent/core_agent/requirements.txt

verify-agent-ci:
	$(MAKE) run-agent-precommit
	$(MAKE) test-agent


### BigQuery MCP Commands ###

run-bq-precommit:
	uvx pre-commit run --files mcp_servers/big_query/**/*

run-bq-tests:
	uv run --group mcp_bq pytest mcp_servers/big_query/tests/

run-bq-mcp-locally:
	uv run --group mcp_bq python -m mcp_servers.big_query.app.main --host localhost --port 8080

build-bq-mcp-image:
	docker build -t test-mcp-server -f mcp_servers/big_query/Dockerfile .

verify-bq-ci:
	$(MAKE) run-bq-precommit
	$(MAKE) run-bq-tests
	$(MAKE) build-bq-mcp-image



### Drive MCP Commands ###

run-drive-precommit:
	uvx pre-commit run --files mcp_servers/google_drive/**/*

run-drive-tests:
	uv run --group mcp_drive pytest mcp_servers/google_drive/tests/

run-drive-mcp-locally:
	uv run --group mcp_drive python -m mcp_servers.google_drive.app.main --host localhost --port 8081

build-drive-mcp-image:
	docker build -t test-drive-mcp-server -f mcp_servers/google_drive/Dockerfile .

verify-drive-ci:
	$(MAKE) run-drive-precommit
	$(MAKE) run-drive-tests
	$(MAKE) build-drive-mcp-image
### GCS MCP Commands ###

run-gcs-precommit:
	uvx pre-commit run --files mcp_servers/gcs/**/*

run-gcs-tests:
	uv run --group mcp_gcs pytest mcp_servers/gcs/tests/

run-gcs-mcp-locally:
	uv run --group mcp_gcs python -m mcp_servers.gcs.app.main --host localhost --port 8082

run-gcs-mcp-smoke:
	uv run --group mcp_gcs python mcp_servers/gcs/scripts/mcp_smoke_test.py --endpoint http://localhost:8082/mcp --bucket $(BUCKET) --prefix $(PREFIX)$(if $(BUCKET_PREFIX), --bucket-prefix $(BUCKET_PREFIX),)

build-gcs-mcp-image:
	docker build -t test-gcs-mcp-server -f mcp_servers/gcs/Dockerfile .

verify-gcs-ci:
	$(MAKE) run-gcs-precommit
	$(MAKE) run-gcs-tests
	$(MAKE) build-gcs-mcp-image
	$(MAKE) test-gcs-terraform

test-gcs-terraform:
	cd terraform/gcs_mcp_server_resources && rm -rf .terraform .terraform.lock.hcl && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

### Google Calendar & Meet MCP Commands ###

run-calendar-precommit:
	uvx pre-commit run --files mcp_servers/google_calendar/**/*

run-calendar-tests:
	uv run --group mcp_calendar pytest mcp_servers/google_calendar/tests/

run-calendar-mcp-locally:
	uv run --group mcp_calendar python -m mcp_servers.google_calendar.app.main --host localhost --port 8083

build-calendar-mcp-image:
	docker build -t test-calendar-mcp-server -f mcp_servers/google_calendar/Dockerfile .

verify-calendar-ci:
	$(MAKE) run-calendar-precommit
	$(MAKE) run-calendar-tests
	$(MAKE) build-calendar-mcp-image

### Metrics Plugin Commands ###

run-metrics-precommit:
	uvx pre-commit run --files agent/plugins/metrics/**/*

run-metrics-tests:
	cd agent && uv run --group ai-agent --group dev pytest tests/plugins/test_metrics_plugin.py

verify-metrics-ci:
	$(MAKE) run-metrics-precommit
	$(MAKE) run-metrics-tests
	$(MAKE) test-metrics-terraform

test-metrics-terraform:
	cd terraform/ai_agent_resources && rm -rf .terraform .terraform.lock.hcl && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

### OneDrive MCP Commands ###

run-onedrive-precommit:
	uvx pre-commit run --files mcp_servers/onedrive/**/*

run-onedrive-tests:
	uv run --group mcp_onedrive pytest mcp_servers/onedrive/tests/

run-onedrive-mcp-locally:
	uv run --group mcp_onedrive python -m mcp_servers.onedrive.app.main --host localhost --port 8084

build-onedrive-mcp-image:
	docker build -t test-onedrive-mcp-server -f mcp_servers/onedrive/Dockerfile .

verify-onedrive-ci:
	$(MAKE) run-onedrive-precommit
	$(MAKE) run-onedrive-tests
	$(MAKE) build-onedrive-mcp-image
	$(MAKE) test-onedrive-terraform

test-onedrive-terraform:
	cd terraform/onedrive_mcp_server_resources && rm -rf .terraform .terraform.lock.hcl && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

### SharePoint MCP Commands ###

run-sharepoint-precommit:
	uvx pre-commit run --files mcp_servers/sharepoint/**/*

run-sharepoint-tests:
	uv run --group mcp_sharepoint pytest mcp_servers/sharepoint/tests/

run-sharepoint-mcp-locally:
	uv run --group mcp_sharepoint python -m mcp_servers.sharepoint.app.main --host localhost --port 8086

build-sharepoint-mcp-image:
	docker build -t test-sharepoint-mcp-server -f mcp_servers/sharepoint/Dockerfile .

verify-sharepoint-ci:
	$(MAKE) run-sharepoint-precommit
	$(MAKE) run-sharepoint-tests
	$(MAKE) build-sharepoint-mcp-image
	$(MAKE) test-sharepoint-terraform

test-sharepoint-terraform:
	cd terraform/sharepoint_mcp_server_resources && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

### EKB Pipeline Commands ###

run-ekb-precommit:
	uvx ruff check pipelines/enterprise_knowledge_base
	uvx ruff format --check pipelines/enterprise_knowledge_base

run-ekb-tests:
	uv run --group classification_pipeline --group rag_pipeline --group ekb-integration pytest pipelines/enterprise_knowledge_base/tests/

build-ekb-image:
	docker build -t ekb-pipeline-test -f pipelines/enterprise_knowledge_base/Dockerfile .

verify-ekb-ci:
	$(MAKE) run-ekb-precommit
	$(MAKE) run-ekb-tests
	$(MAKE) build-ekb-image
	$(MAKE) test-ekb-terraform

test-ekb-terraform:
	cd terraform/ekb_pipeline_resources && rm -rf .terraform .terraform.lock.hcl && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

### Atlassian MCP Commands ###

run-atlassian-precommit:
	uvx pre-commit run --files mcp_servers/atlassian/**/*

run-atlassian-tests:
	uv run --group mcp_atlassian pytest mcp_servers/atlassian/tests/

run-atlassian-mcp-locally:
	uv run --group mcp_atlassian python -m mcp_servers.atlassian.app.main --host localhost --port 8085

run-atlassian-mcp-smoke:
	uv run --group mcp_atlassian python mcp_servers/atlassian/scripts/mcp_smoke_test.py --endpoint http://localhost:8085/mcp

run-atlassian-mcp-test-client:
	uv run --group mcp_atlassian python mcp_servers/atlassian/scripts/test_mcp_client.py

build-atlassian-mcp-image:
	docker build -t test-atlassian-mcp-server -f mcp_servers/atlassian/Dockerfile .

verify-atlassian-ci:
	$(MAKE) run-atlassian-precommit
	$(MAKE) run-atlassian-tests
	$(MAKE) run-atlassian-mcp-test-client
	$(MAKE) build-atlassian-mcp-image
	$(MAKE) test-atlassian-terraform

test-atlassian-terraform:
	cd terraform/atlassian_mcp_server_resources && terraform fmt -check -recursive && terraform init -backend=false && terraform validate
