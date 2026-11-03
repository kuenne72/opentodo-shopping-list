import httpx

from app import config, sections
from app.opentodo_client import OpenTodoClient


def test_sections_refresh_and_fallback():
    rows = [
        {"id": "s2", "name": "Tiefkühl", "project_id": config.settings.project_id, "position": 2, "deleted_at": None},
        {"id": "s1", "name": "Obst/Gemüse", "project_id": config.settings.project_id, "position": 1, "deleted_at": None},
        {"id": "x", "name": "fremd", "project_id": "P9", "position": 0, "deleted_at": None},
        {"id": "s3", "name": "Sonstiges", "project_id": config.settings.project_id, "position": 3, "deleted_at": None},
    ]
    c = OpenTodoClient("https://ot", "t", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"sections": rows})))
    got = sections.refresh(c)
    assert [s["name"] for s in got] == ["Obst/Gemüse", "Tiefkühl", "Sonstiges"]
    assert sections.id_for("Tiefkühl") == "s2"
    assert sections.fallback_id() == "s3"
    assert sections.default_meta("Tiefkühl") == ("tag", "grey")
    assert sections.default_meta("Obst/Gemüse") == ("apple", "green")
