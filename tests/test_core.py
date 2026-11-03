import json
import re
from pathlib import Path

import httpx
import pytest

from app import config
from tests.conftest import SECTION_IDS
from app.core import ShoppingList, parse_quick
from app.db import Database
from app.opentodo_client import OpenTodoClient

BASE = "https://ot.test"


@pytest.mark.parametrize(
    "text,name,qty,unit",
    [
        ("Milch", "Milch", None, None),
        ("2 Milch", "Milch", 2, None),
        ("2x Milch", "Milch", 2, "Stk"),
        ("500 g Hackfleisch", "Hackfleisch", 500, "g"),
        ("1,5 l Cola", "Cola", 1.5, "l"),
        ("Milch 2 l", "Milch", 2, "l"),
        ("2 Bio Eier", "Bio Eier", 2, None),
        ("3 Pck Butter", "Butter", 3, "Pck"),
        ("Cola Zero", "Cola Zero", None, None),
        ("3 pcs Butter", "Butter", 3, "Stk"),
        ("2 packs Pasta", "Pasta", 2, "Pck"),
    ],
)
def test_parse_quick(text, name, qty, unit):
    q = parse_quick(text)
    assert (q.name, q.qty, q.unit) == (name, qty, unit)


class FakeServer:
    """Minimaler OpenTodo-Ersatz für /api/v1/tasks."""

    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self.n = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/api/v1/tasks":
            return httpx.Response(200, json={"tasks": list(self.tasks.values())})
        if request.method == "POST" and path == "/api/v1/tasks":
            body = json.loads(request.content)
            self.n += 1
            t = {
                "id": f"t{self.n:03d}-0000-0000-0000-000000000000",
                "completed_at": None, "deleted_at": None, "labels": [], "fields": {},
            } | body
            self.tasks[t["id"]] = t
            return httpx.Response(201, json=t)
        m = re.match(r"/api/v1/tasks/(.+)", path)
        if request.method == "PATCH" and m:
            t = self.tasks[m.group(1)]
            body = json.loads(request.content)
            fields = body.pop("fields", None)
            t.update(body)
            if fields:
                for k, v in fields.items():
                    if v is None:
                        t["fields"].pop(k, None)
                    else:
                        t["fields"][k] = v
            return httpx.Response(200, json=t)
        return httpx.Response(404, json={"error": "not_found"})


@pytest.fixture
def env(tmp_path: Path):
    srv = FakeServer()
    client = OpenTodoClient(BASE, "ot_test", transport=httpx.MockTransport(srv.handler))
    db = Database(tmp_path / "e.db")
    db.upsert_item("Milch", aliases=["Vollmilch"], default_qty=1, unit="l", section_id=SECTION_IDS["Kühlregal"])
    sl = ShoppingList(client, db, project_id="P1")
    return srv, db, sl


def test_add_known_item_uses_stammdaten(env):
    srv, db, sl = env
    t = sl.add("Vollmilch")
    assert t["title"] == "Milch"
    assert t["section_id"] == SECTION_IDS["Kühlregal"]
    assert t["fields"] == {config.FIELD_MENGE: 1, config.FIELD_EINHEIT: "l"}


def test_add_merges_quantity(env):
    srv, db, sl = env
    sl.add("2 l Milch")
    t = sl.add("1 l Milch")
    assert len(srv.tasks) == 1
    assert t["fields"][config.FIELD_MENGE] == 3


def test_add_unknown_item_goes_to_sonstiges_and_stamm(env):
    srv, db, sl = env
    t = sl.add("3 Pck Kerzen")
    assert t["section_id"] == SECTION_IDS["Sonstiges"]
    assert db.find_item("kerzen")["unit"] == "Pck"


def test_view_sorted_by_store_order(env):
    srv, db, sl = env
    sl.add("Milch"); sl.add("Äpfel"); sl.add("Brot")
    db.upsert_item("Äpfel", section_id=SECTION_IDS["Obst/Gemüse"])
    db.upsert_item("Brot", section_id=SECTION_IDS["Brot/Backwaren"])
    # Sections der schon angelegten Aufgaben nachziehen
    for t in srv.tasks.values():
        it = db.find_item(t["title"])
        t["section_id"] = it["section_id"]
    sid = db.upsert_store("Edeka")
    db.set_store_order(sid, [SECTION_IDS["Brot/Backwaren"], SECTION_IDS["Kühlregal"], SECTION_IDS["Obst/Gemüse"]])
    assert [r["title"] for r in sl.view("Edeka")] == ["Brot", "Milch", "Äpfel"]
    assert [r["title"] for r in sl.view()] == ["Äpfel", "Brot", "Milch"]


def test_check_and_template(env):
    srv, db, sl = env
    db.upsert_item("Eier", unit="Stk", section_id=SECTION_IDS["Kühlregal"])
    db.upsert_template("Wochenende", [(db.find_item("Milch")["id"], 2, None), (db.find_item("Eier")["id"], 10, "Stk")])
    out = sl.apply_template("Wochenende")
    assert {t["title"] for t in out} == {"Milch", "Eier"}
    assert out[1]["fields"][config.FIELD_MENGE] == 10
    sl.check(out[0]["id"])
    assert srv.tasks[out[0]["id"]]["completed_at"]
    assert len(sl.open_tasks()) == 1


def test_user_token_roundtrip(tmp_path):
    from cryptography.fernet import Fernet
    db = Database(tmp_path / "u.db", Fernet.generate_key().decode())
    db.set_user_token("Anna", "ot_abc")
    assert db.user_token("Anna") == "ot_abc"
    assert db.user_token("Niemand") is None


def test_store_view_limits_to_store_sections(env):
    srv, db, sl = env
    sl.add("Milch"); sl.add("Schrauben")
    db.upsert_item("Schrauben", section_id=SECTION_IDS["Sonstiges"])
    for t in srv.tasks.values():
        t["section_id"] = db.find_item(t["title"])["section_id"]
    sid = db.upsert_store("Baumarkt")
    db.set_store_order(sid, [SECTION_IDS["Sonstiges"]])
    assert [r["title"] for r in sl.view("Baumarkt")] == ["Schrauben"]
    assert len(sl.view()) == 2


def test_store_assignment_in_service(env):
    srv, db, sl = env
    db.upsert_store("Supermarkt"); db.upsert_store("Baumarkt")
    t1 = sl.add("Milch", store="Supermarkt")
    t2 = sl.add("Schrauben", store="Baumarkt")
    t3 = sl.add("Kerzen")                      # kein Laden -> überall
    assert t1.get("labels", []) == [] and t2.get("labels", []) == []   # keine OpenTodo-Labels
    assert {r["title"] for r in sl.view("Supermarkt")} == {"Milch", "Kerzen"}
    assert {r["title"] for r in sl.view("Baumarkt")} == {"Schrauben", "Kerzen"}
    assert [r["stores"] for r in sl.view() if r["title"] == "Milch"] == [["Supermarkt"]]
    sl.add("Milch", store="Baumarkt")          # Merge ergänzt den zweiten Laden
    assert sorted(next(r["stores"] for r in sl.view() if r["title"] == "Milch")) == ["Baumarkt", "Supermarkt"]
