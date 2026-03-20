PROJECT_ID=p-dev-gce-60pf
REGION=us-central1

### General Commands ###

gcloud-auth:
	gcloud auth application-default login --project=$(PROJECT_ID)
	gcloud config set project $(PROJECT_ID)

install-precommit:
	uvx pre-commit install

run-precommit:
	uvx pre-commit run --all-files

verify-all-ci:
	$(MAKE) verify-agent-ci
	$(MAKE) verify-bq-ci
	$(MAKE) verify-gcs-ci
	$(MAKE) verify-drive-ci

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
	uv run --group ai-agent adk web --port 8000

deploy-agent:
	uv export \
		--group ai-agent \
		--no-hashes \
		--no-annotate \
		-o agent/core_agent/requirements.txt
	uv run --group ai-agent --group dev python -m agent.deployment.deploy \
		--project ${PROJECT_ID} \
		--location ${REGION} \
		--display-name "Production Research Agent" \
		--source-packages=./agent \
		--entrypoint-module=agent.core_agent.agent \
		--entrypoint-object=app \
		--requirements-file=./agent/core_agent/requirements.txt \
		--service-account=adk-agent@p-dev-gce-60pf.iam.gserviceaccount.com \
		--set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},MODEL_ARMOR_TEMPLATE_ID=security-template"
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
	uv run --group mcp_gcs python -m mcp_servers.gcs.app.main --host localhost --port 8080

run-gcs-mcp-smoke:
	uv run --group mcp_gcs python mcp_servers/gcs/scripts/mcp_smoke_test.py --endpoint http://localhost:8080/mcp --bucket $(BUCKET) --prefix $(PREFIX)$(if $(BUCKET_PREFIX), --bucket-prefix $(BUCKET_PREFIX),)

build-gcs-mcp-image:
	docker build -t test-gcs-mcp-server -f mcp_servers/gcs/Dockerfile .

verify-gcs-ci:
	$(MAKE) run-gcs-precommit
	$(MAKE) run-gcs-tests
	$(MAKE) build-gcs-mcp-image
	$(MAKE) test-gcs-terraform

test-gcs-terraform:
	cd terraform/gcs_mcp_server_resources && terraform fmt -check -recursive && terraform init -backend=false && terraform test
