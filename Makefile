PROJECT_ID=p-dev-gce-60pf

gcloud-auth:
	gcloud auth application-default login --project=p-dev-gce-60pf
	gcloud config set project $(PROJECT_ID)

run-ui-agent:
	cd agent && \
	uv run adk web --port 8000
