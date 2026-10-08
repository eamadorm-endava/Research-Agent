"""Verify creation/reconciliation behavior rather than just Terraform syntax."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from terraform.scripts import discover_gateway_imports as gateway
from terraform.scripts import discover_ui_imports as ui
from terraform.scripts import ensure_embedding_model as model

CONFIG = {
    "project_id": "example-project",
    "region": "us-central1",
    "dataset_id": "kb",
    "connection_id": "vertex",
}


def response(status, body=None):
    return model.ApiResponse(status, __import__("json").dumps(body or {}).encode())


def test_existing_model_is_not_recreated():
    session = MagicMock()
    session.get.return_value = response(200)
    model.ensure_model(CONFIG, session)
    session.post.assert_not_called()


def test_model_read_permission_failure_is_not_reported_as_missing():
    session = MagicMock()
    session.get.return_value = response(403)
    with pytest.raises(RuntimeError, match="403"):
        model.ensure_model(CONFIG, session)
    session.post.assert_not_called()


def test_transient_creation_failure_retries_and_verifies(monkeypatch):
    monkeypatch.setattr(model.time, "sleep", lambda _: None)
    session = MagicMock()
    session.get.side_effect = [response(404), response(200)]
    session.post.side_effect = [response(403), response(200)]
    model.ensure_model(CONFIG, session)
    assert session.post.call_count == 2
    assert (
        "CREATE MODEL IF NOT EXISTS" in session.post.call_args.kwargs["json"]["query"]
    )


def test_creation_never_reports_success_without_model(monkeypatch):
    monkeypatch.setattr(model.time, "sleep", lambda _: None)
    session = MagicMock()
    session.get.return_value = response(404)
    session.post.return_value = response(200, {"jobComplete": False})
    with pytest.raises(RuntimeError, match="10 attempts"):
        model.ensure_model(CONFIG, session)
    assert session.post.call_count == 10


def test_existing_subnet_must_match_network_cidr_and_purpose(monkeypatch):
    monkeypatch.setattr(
        gateway,
        "describe",
        lambda kind, name, project, region=None: (
            {"autoCreateSubnetworks": False}
            if region is None
            else {
                "ipCidrRange": "192.168.0.0/24",
                "purpose": "PRIVATE",
                "network": "projects/project/global/networks/mcp-agent-vpc",
            }
        ),
    )
    with pytest.raises(ValueError, match="does not match"):
        gateway.discover(
            "project", "us-central1", "mcp-agent-vpc", "10.10.0.0/24", "10.129.0.0/23"
        )


def test_existing_ui_test_service_has_correct_import_address(monkeypatch):
    monkeypatch.setattr(
        ui.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="test-ui-backend\n", stderr=""
        ),
    )
    imports = ui.discover("backend", "project", "us-central1")
    assert imports == [
        (
            'module.ui_backend_cloud_run["test"].google_cloud_run_v2_service.service[0]',
            "projects/project/locations/us-central1/services/test-ui-backend",
        )
    ]


def test_ui_discovery_does_not_hide_permission_errors(monkeypatch):
    monkeypatch.setattr(
        ui.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="PERMISSION_DENIED"
        ),
    )
    with pytest.raises(RuntimeError, match="Cannot inspect"):
        ui.discover("frontend", "project", "us-central1")
