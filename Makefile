PROJECT_ID=p-dev-gce-60pf

gcloud-auth:
	gcloud auth application-default login
	gcloud auth application-default set-quota-project $(PROJECT_ID)