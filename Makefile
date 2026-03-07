PROJECT_ID=p-dev-gce-60pf

gcloud-auth:
	gcloud auth application-default login --project=p-dev-gce-60pf
	gcloud config set project $(PROJECT_ID)

run-ui-agent:
	cd agent && \
	uv run adk web --port 8000

install-precommit:
	uvx pre-commit install

run-precommit:
	uvx pre-commit run --all-files

### BigQuery MCP Commands ###

run-bq-precommit:
	uvx pre-commit run --files mcp_servers/big_query/**/*

run-bq-tests:
	uv run --group mcp_bq pytest mcp_servers/big_query/tests/

run-bq-mcp-locally:
	uv run --group mcp_bq uvicorn mcp_servers.big_query.app.main:app --host 0.0.0.0 --port 8080 --reload

build-bq-mcp-image:
	docker build -t test-mcp-server -f mcp_servers/big_query/Dockerfile .

