import json

import httpx

from app import bootstrap, config, sections
from app.opentodo_client import OpenTodoClient


def _client(projects, fields, secs=None, created=None):
    secs = secs if secs is not None else []

    def handler(r: httpx.Request) -> httpx.Response:
        p = r.url.path
        if p == "/api/v1/projects":
            return httpx.Response(200, json={"projects": projects})
        if p == "/api/v1/fields":
            return httpx.Response(200, json={"fields": fields})
        if p == "/api/v1/sections" and r.method == "GET":
            return httpx.Response(200, json={"sections": secs})
        if p == "/api/v1/sections" and r.method == "POST":
            b = json.loads(r.content)
            created.append(b["name"])
            return httpx.Response(201, json={"id": f"s{len(created)}", **b, "deleted_at": None})
        return httpx.Response(404, json={})

    return OpenTodoClient("https://ot", "t", transport=httpx.MockTransport(handler))


PROJ = [{"id": "PX", "name": "Shopping", "deleted_at": None}, {"id": "PY", "name": "Work"}]
FLD = [{"id": "fm", "name": "Quantity", "project_id": "PX"}, {"id": "fe", "name": "Unit", "project_id": "PX"}]


def test_resolve_by_name_and_english_fields(monkeypatch):
    config.settings.project_id = ""
    monkeypatch.setattr(config.settings, "project_name", "shopping")
    rep = bootstrap.resolve(_client(PROJ, FLD))
    assert rep.ok and config.settings.project_id == "PX"
    assert (config.FIELD_MENGE, config.FIELD_EINHEIT) == ("fm", "fe")
    assert rep.fields["FIELD_PREIS"] is False   # optional


def test_resolve_reports_missing(monkeypatch):
    config.settings.project_id = ""
    monkeypatch.setattr(config.settings, "project_name", "Nope")
    rep = bootstrap.resolve(_client(PROJ, FLD))
    assert not rep.ok and "Nope" in rep.problems[0]
    config.settings.project_id = "PX"
    rep = bootstrap.resolve(_client(PROJ, FLD[:1]))
    assert any("Unit" in p or "einheit" in p for p in rep.problems)


def test_setup_creates_default_sections_once():
    config.settings.project_id = "PX"
    created: list[str] = []
    rep, made = bootstrap.setup(_client(PROJ, FLD, created=created), "en")
    assert made == created == sections.default_section_names("en") and len(made) == 8
    created2: list[str] = []
    secs = [{"id": "a", "name": "Produce", "project_id": "PX", "position": 0, "deleted_at": None}]
    _, made2 = bootstrap.setup(_client(PROJ, FLD, secs=secs, created=created2), "en")
    assert made2 == []
