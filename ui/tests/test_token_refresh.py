"""Expired-token and distributed-lease regressions without credential/network access."""

import importlib
import time
from threading import Event, Thread
from unittest.mock import MagicMock

from agent.core_agent.security.token_store import (
    GoogleRefreshStrategy,
    TokenData,
    TokenStore,
)


def test_valid_tokens_do_not_refresh(database):
    store = TokenStore(project_id="test-project")
    store._db = database
    store.save_tokens(
        "alice",
        "google",
        TokenData(access_token="valid", expires_at=time.time() + 3600),
    )
    store.refresh_strategies["google"] = MagicMock()
    assert store.get_valid_access_token("alice", "google") == "valid"
    store.refresh_strategies["google"].refresh_token.assert_not_called()


def test_missing_refresh_token_does_not_attempt_exchange(database):
    store = TokenStore(project_id="test-project")
    store._db = database
    store.save_tokens("alice", "google", TokenData(access_token="old", expires_at=1))
    store.refresh_strategies["google"] = MagicMock()
    assert store.get_valid_access_token("alice", "google") is None
    store.refresh_strategies["google"].refresh_token.assert_not_called()


def test_concurrent_refresh_rotates_credentials_only_once(database):
    stores = [TokenStore(project_id="test-project") for _ in range(2)]
    for store in stores:
        store._db = database
    stores[0].save_tokens(
        "alice",
        "google",
        TokenData(access_token="old", refresh_token="old-refresh", expires_at=1),
    )
    entered, finish, competing = Event(), Event(), Event()

    def refresh(old_refresh):
        assert old_refresh == "old-refresh"
        entered.set()
        assert finish.wait(5)
        return TokenData(
            access_token="new",
            refresh_token="rotated-refresh",
            expires_at=time.time() + 3600,
        )

    strategy = MagicMock()
    strategy.refresh_token.side_effect = refresh
    for store in stores:
        store.refresh_strategies["google"] = strategy
    original_acquire = stores[1]._acquire_lease

    def observe_competitor(*args):
        acquired = original_acquire(*args)
        competing.set()
        return acquired

    stores[1]._acquire_lease = observe_competitor
    results = []
    first = Thread(
        target=lambda: results.append(
            stores[0].get_valid_access_token("alice", "google")
        )
    )
    second = Thread(
        target=lambda: results.append(
            stores[1].get_valid_access_token("alice", "google")
        )
    )
    first.start()
    assert entered.wait(5)
    second.start()
    assert competing.wait(5)
    finish.set()
    first.join(5)
    second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert results == ["new", "new"]
    strategy.refresh_token.assert_called_once_with("old-refresh")
    assert (
        stores[0].get_token_data("alice", "google").refresh_token == "rotated-refresh"
    )


def test_refresh_http_request_has_a_timeout(monkeypatch):
    post = MagicMock()
    post.return_value.json.return_value = {"access_token": "new", "expires_in": 3600}
    monkeypatch.setattr(
        importlib.import_module("agent.core_agent.security.token_store").requests,
        "post",
        post,
    )
    assert GoogleRefreshStrategy().refresh_token("refresh").access_token == "new"
    assert post.call_args.kwargs["timeout"] == 20


def test_reconnect_completed_during_refresh_is_not_overwritten(database):
    store = TokenStore(project_id="test-project")
    store._db = database
    expired = TokenData(access_token="old", refresh_token="old-refresh", expires_at=1)
    store.save_tokens("alice", "google", expired)
    reconnected = TokenData(
        access_token="reconnected",
        refresh_token="new-account-refresh",
        expires_at=time.time() + 3600,
    )

    def refresh(_):
        store.save_tokens("alice", "google", reconnected)
        return TokenData(
            access_token="stale-result",
            refresh_token="rotated-old-refresh",
            expires_at=time.time() + 3600,
        )

    store.refresh_strategies["google"] = MagicMock()
    store.refresh_strategies["google"].refresh_token.side_effect = refresh
    assert store.get_valid_access_token("alice", "google") == "reconnected"
    assert (
        store.get_token_data("alice", "google").refresh_token == "new-account-refresh"
    )
