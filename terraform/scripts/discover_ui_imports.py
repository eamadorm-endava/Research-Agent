"""Adopt only the existing test services that were previously deployed outside Terraform."""

import subprocess
import sys


def discover(component: str, project: str, region: str):
    """An absent test service is created normally; other read failures stop deployment."""
    if component not in {"backend", "frontend"}:
        raise ValueError("Unknown UI component")
    name = f"test-ui-{component}"
    result = subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            name,
            f"--project={project}",
            f"--region={region}",
            "--format=value(metadata.name)",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        error = result.stderr.lower()
        if "not found" in error or "not_found" in error:
            return []
        raise RuntimeError(f"Cannot inspect existing service {name}")
    if result.stdout.strip() != name:
        raise ValueError("Unexpected Cloud Run service identity")
    address = f'module.ui_{component}_cloud_run["test"].google_cloud_run_v2_service.service[0]'
    return [(address, f"projects/{project}/locations/{region}/services/{name}")]


if __name__ == "__main__":
    for address, resource_id in discover(*sys.argv[1:]):
        print(address, resource_id)
