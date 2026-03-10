PROJECT_ID=p-dev-gce-60pf
REGION=us-central1

gcloud-auth:
	gcloud auth application-default login --project=$(PROJECT_ID)
	gcloud config set project $(PROJECT_ID)

install-precommit:
	uvx pre-commit install

run-precommit:
	uvx pre-commit run --all-files

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


### BigQuery MCP Commands ###

run-bq-precommit:
	uvx pre-commit run --files mcp_servers/big_query/**/*

run-bq-tests:
	uv run --group mcp_bq pytest mcp_servers/big_query/tests/

run-bq-mcp-locally:
	uv run --group mcp_bq python -m mcp_servers.big_query.app.main --host localhost --port 8080

build-bq-mcp-image:
	docker build -t test-mcp-server -f mcp_servers/big_query/Dockerfile .

