"""Guard against applying production state from PRs or retired UI triggers."""

from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize(
    "configuration",
    [
        "terraform/ui_backend_resources/ui-backend-services-cloud-build-ci.yaml",
        "terraform/ui_frontend_resources/ui-frontend-services-cloud-build-ci.yaml",
        "terraform/ui_backend_resources/ui-backend-services-cloud-build-cd.yaml",
    ],
)
def test_read_only_builds_never_apply_or_deploy(configuration):
    build = yaml.safe_load(Path(configuration).read_text())
    for step in build["steps"]:
        arguments = " ".join(step.get("args", []))
        assert "apply" not in arguments
        assert "gcloud run deploy" not in arguments
        assert "terraform import" not in arguments


def test_coordinated_build_orders_resources_before_frontend():
    build = yaml.safe_load(
        Path(
            "terraform/ui_frontend_resources/ui-frontend-services-cloud-build-cd.yaml"
        ).read_text()
    )
    steps = [step["id"] for step in build["steps"]]
    assert (
        steps.index("shared-apply")
        < steps.index("ensure-model")
        < steps.index("gateway-apply")
    )
    assert (
        steps.index("gateway-apply")
        < steps.index("backend-apply")
        < steps.index("frontend-apply")
    )
    assert steps.index("backend-import") < steps.index("backend-plan")
    assert steps.index("frontend-import") < steps.index("frontend-plan")
