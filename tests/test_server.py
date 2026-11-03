import json
import time

import pytest

from app import webhook as wh
from app.cache import ListCache


# ---------------------------------------------------------------- Signatur
def test_sign_verify_roundtrip():
    secret = "whsec_test"
    body = b'{"event":"ping"}'
    ts = int(time.time())
    sig = wh.sign(secret, ts, body)
    assert sig.startswith("v1=") and len(sig) == 3 + 64
    assert wh.verify(secret, str(ts), body, sig)
    assert not wh.verify(secret, str(ts), body + b" ", sig)
    assert not wh.verify("whsec_other", str(ts), body, sig)
    assert not wh.verify(secret, str(ts - 1000), body, wh.sign(secret, ts - 1000, body))
    assert not wh.verify("", str(ts), body, sig)
    assert not wh.verify(secret, None, body, sig)


# ---------------------------------------------------------------- Cache
def _task(tid, title, project="P1", **kw):
    return {"id": tid, "title": title, "project_id": project, "completed_at": None, "deleted_at": None} | kw


def test_cache_events_and_dedupe():
    c = ListCache("P1")
    c.replace_all([_task("a", "Milch"), _task("b", "Brot"), _task("x", "fremd", project="P2")])
    assert {t["id"] for t in c.tasks()} == {"a", "b"}
    v = c.version

    assert c.apply_event("d1", "task.created", _task("c", "Eier"))
    assert not c.apply_event("d1", "task.created", _task("c", "Eier"))  # Duplikat
    assert len(c.tasks()) == 3 and c.version == v + 1

    assert c.apply_event("d2", "task.completed", _task("a", "Milch", completed_at=123))
    assert {t["id"] for t in c.tasks()} == {"b", "c"}
    assert len(c.tasks(open_only=False)) == 3

    assert c.apply_event("d3", "task.deleted", _task("b", "Brot", deleted_at=1))
    assert {t["id"] for t in c.tasks()} == {"c"}

    assert not c.apply_event("d4", "task.created", _task("z", "woanders", project="P2"))
    assert not c.apply_event("d5", "project.updated", None)


# ---------------------------------------------------------------- Server
@pytest.fixture
def client(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("EINKAUF_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("EINKAUF_SECRET", Fernet.generate_key().decode())
    monkeypatch.setenv("EINKAUF_WEBHOOK_SECRET", "whsec_test")
    import importlib
    from app import config
    importlib.reload(config)
    from app import server
    importlib.reload(server)
    from fastapi.testclient import TestClient
    # ohne Benutzer: Start ohne Vollabgleich
    with TestClient(server.app) as tc:
        yield tc, server


def _post_webhook(tc, payload: dict, secret="whsec_test", ts=None):
    body = json.dumps(payload).encode()
    ts = ts or int(time.time())
    return tc.post(
        "/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-OpenTodo-Timestamp": str(ts),
            "X-OpenTodo-Signature": wh.sign(secret, ts, body),
        },
    )


def test_webhook_rejects_bad_signature(client):
    tc, server = client
    r = _post_webhook(tc, {"id": "d1", "event": "ping", "data": {}}, secret="whsec_wrong")
    assert r.status_code == 401


def test_webhook_ping_and_task(client):
    tc, server = client
    r = _post_webhook(tc, {"id": "d1", "event": "ping", "data": {}})
    assert r.status_code == 200 and r.json()["ping"]

    pid = server.config.settings.project_id
    r = _post_webhook(tc, {"id": "d2", "event": "task.created", "data": {"task": _task("t1", "Milch", project=pid)}})
    assert r.json()["applied"] is True
    assert server.cache.tasks()[0]["title"] == "Milch"

    r = _post_webhook(tc, {"id": "d2", "event": "task.created", "data": {"task": _task("t1", "Milch", project=pid)}})
    assert r.json()["applied"] is False  # Duplikat

    s = tc.get("/api/status").json()
    assert s["open"] == 1 and s["version"] >= 1


def test_api_requires_user(client):
    tc, _ = client
    assert tc.get("/api/list").status_code == 400
    assert tc.get("/api/list", headers={"X-Einkauf-User": "Niemand"}).status_code == 401
