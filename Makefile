PROJECT_ID=p-dev-gce-60pf

gcloud-auth:
	gcloud auth application-default login
	gcloud config set project $(PROJECT_ID)
	gcloud auth application-default set-quota-project $(PROJECT_ID)

run-web-dev:
	adk web --port 8000 