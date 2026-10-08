"""Discover and validate existing gateway objects before importing missing state."""

import json
import subprocess
import sys


def describe(kind, name, project, region=None):
    """Read an existing object; only an explicit not-found means a new deployment."""
    command = [
        "gcloud",
        "compute",
        *kind,
        "describe",
        name,
        f"--project={project}",
        "--format=json",
    ]
    if region:
        command.append(f"--region={region}")
    result = subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=60
    )
    if result.returncode:
        if (
            "not found" in result.stderr.lower()
            or "was not found" in result.stderr.lower()
        ):
            return None
        raise RuntimeError(f"Cannot inspect gateway resource {name}")
    return json.loads(result.stdout)


def discover(project, region, network, app_cidr, proxy_cidr):
    """Reject an incompatible existing network/subnet instead of adopting it silently."""
    found = []
    vpc = describe(["networks"], network, project)
    if vpc:
        if vpc.get("autoCreateSubnetworks"):
            raise ValueError("Existing gateway network is not a custom VPC")
        found.append(
            (
                "google_compute_network.vpc",
                f"projects/{project}/global/networks/{network}",
            )
        )
    for key, suffix, cidr, purpose in [
        ("app_subnet", "app-subnet", app_cidr, "PRIVATE"),
        (
            "proxy_only_subnet",
            "proxy-only-subnet",
            proxy_cidr,
            "REGIONAL_MANAGED_PROXY",
        ),
    ]:
        name = f"{network}-{suffix}-{region}"
        subnet = describe(["networks", "subnets"], name, project, region)
        if subnet:
            if (
                subnet["ipCidrRange"] != cidr
                or subnet.get("purpose", "PRIVATE") != purpose
                or not subnet["network"].endswith(f"/networks/{network}")
            ):
                raise ValueError(
                    f"Existing subnet {name} does not match gateway configuration"
                )
            found.append(
                (
                    f"google_compute_subnetwork.{key}",
                    f"projects/{project}/regions/{region}/subnetworks/{name}",
                )
            )
    return found


if __name__ == "__main__":
    for address, resource_id in discover(*sys.argv[1:]):
        print(address, resource_id)
