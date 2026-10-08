"""Ensure the remote embedding model exists using Cloud SDK ADC, after apply."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request


class ApiResponse:
    """Expose only the HTTP response needed by the idempotent model check."""

    def __init__(self, status, body):
        self.status_code = status
        self.body = body
        self.ok = 200 <= status < 300

    def json(self):
        return json.loads(self.body)

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(f"BigQuery request failed (HTTP {self.status_code})")


class CloudSdkSession:
    """Use Cloud SDK credentials without relying on its vendored Python packages."""

    def __init__(self):
        command = ["gcloud", "auth", "print-access-token"]
        if target := os.getenv("GOOGLE_IMPERSONATE_SERVICE_ACCOUNT"):
            command.append(f"--impersonate-service-account={target}")
        self.token = subprocess.check_output(command, text=True, timeout=30).strip()

    def request(self, method, url, payload, timeout):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return ApiResponse(response.status, response.read())
        except urllib.error.HTTPError as error:
            return ApiResponse(error.code, error.read())

    def get(self, url, timeout):
        return self.request("GET", url, None, timeout)

    def post(self, url, json, timeout):
        return self.request("POST", url, json, timeout)


def model_exists(session, config):
    """Distinguish a missing model from permission, credential or server errors."""
    url = (
        "https://bigquery.googleapis.com/bigquery/v2/projects/"
        f"{config['project_id']}/datasets/{config['dataset_id']}/models/"
        "multimodal_embedding_model"
    )
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def ensure_model(config, session):
    """Submit an idempotent query with bounded retries for IAM propagation."""
    for key in ("project_id", "region", "dataset_id", "connection_id"):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", config[key]):
            raise ValueError(f"Invalid model configuration: {key}")
    if model_exists(session, config):
        print("Embedding model already exists.")
        return
    query = (
        "CREATE MODEL IF NOT EXISTS "
        f"`{config['project_id']}.{config['dataset_id']}.multimodal_embedding_model` "
        f"REMOTE WITH CONNECTION `{config['project_id']}.{config['region']}."
        f"{config['connection_id']}` OPTIONS (ENDPOINT = 'multimodalembedding@001');"
    )
    url = (
        "https://bigquery.googleapis.com/bigquery/v2/projects/"
        f"{config['project_id']}/queries"
    )
    for attempt in range(1, 11):
        response = session.post(
            url,
            json={
                "query": query,
                "useLegacySql": False,
                "location": config["region"],
                "timeoutMs": 20000,
            },
            timeout=40,
        )
        if response.status_code not in (200, 403, 429, 500, 503):
            response.raise_for_status()
        # jobs.query can return 200 with errors or an unfinished job.
        if (
            response.ok
            and not response.json().get("errors")
            and model_exists(session, config)
        ):
            print("Embedding model verified.")
            return
        print(
            f"Embedding model not ready: attempt {attempt}/10 (HTTP {response.status_code})."
        )
        if attempt < 10:
            time.sleep(30)
    raise RuntimeError("Embedding model creation failed after 10 attempts.")


if __name__ == "__main__":
    with open(sys.argv[1]) as config_file:
        ensure_model(json.load(config_file), CloudSdkSession())
