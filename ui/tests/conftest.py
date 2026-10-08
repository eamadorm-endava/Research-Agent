"""Isolated API tests with a transactional in-memory Firestore substitute."""

from copy import deepcopy
from functools import wraps
from threading import RLock

import pytest
from fastapi.testclient import TestClient


class Snapshot:
    def __init__(self, record):
        self.record = deepcopy(record)
        self.exists = record is not None

    def to_dict(self):
        return deepcopy(self.record)


class Reference:
    def __init__(self, db, key):
        self.db, self.key = db, key

    def get(self, transaction=None):
        return Snapshot(self.db.records.get(self.key))

    def set(self, record, merge=False):
        if merge:
            self.db.records.setdefault(self.key, {}).update(deepcopy(record))
        else:
            self.db.records[self.key] = deepcopy(record)


class Collection:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, key):
        return Reference(self.db, (self.name, key))


class FakeDB:
    def __init__(self):
        self.records, self.lock = {}, RLock()

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return self

    def set(self, reference, record, merge=False):
        reference.set(record, merge=merge)

    def delete(self, reference):
        self.records.pop(reference.key, None)


def transactional(function):
    @wraps(function)
    def invoke(transaction, *args):
        with transaction.lock:
            return function(transaction, *args)

    return invoke


@pytest.fixture
def database(monkeypatch):
    from google.cloud import firestore

    from agent.core_agent.security.token_store import token_store

    db = FakeDB()
    monkeypatch.setattr(firestore, "transactional", transactional)
    monkeypatch.setattr(token_store, "_db", db)
    return db


@pytest.fixture
def config(monkeypatch):
    from ui.backend.config import UI_CONFIG

    for name, value in {
        "PUBLIC_BASE_URL": "https://osiris.example.com",
        "ENVIRONMENT": "production",
        "REQUIRED_PROVIDERS": [],
        "LOCAL_USER_EMAIL": "",
        "REQUESTS_PER_MINUTE": 30,
        "LANDING_ZONE_BUCKET": "private-uploads",
        "SERVICE_ACCOUNT_EMAIL": "backend@example.iam.gserviceaccount.com",
    }.items():
        monkeypatch.setattr(UI_CONFIG, name, value)
    return UI_CONFIG


@pytest.fixture
def client(database, config, monkeypatch):
    from ui.backend.auth import get_current_user
    from ui.backend.main import app
    from ui.backend.routers.oauth import PROVIDER_CONFIGS

    for provider_config in PROVIDER_CONFIGS.values():
        monkeypatch.setattr(provider_config, "CLIENT_ID", "test-client")
        monkeypatch.setattr(provider_config, "CLIENT_SECRET", "test-secret")
    app.dependency_overrides[get_current_user] = lambda: "alice@example.com"
    with TestClient(app, base_url="https://osiris.example.com") as api_client:
        yield api_client
    app.dependency_overrides.clear()
