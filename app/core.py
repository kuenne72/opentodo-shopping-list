"""Kernlogik des Einkaufsdienstes (Plan 3.5, 3.6).

- parse_quick:   "2 Milch", "500 g Hackfleisch", "Brot" -> (Menge, Einheit, Name)
- ShoppingList:  Artikel auf die Liste (mergen), abhaken, Vorlage ausrollen,
                 offene Liste nach Laden sortiert, Historie
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from . import config, sections
from .db import Database
from .opentodo_client import OpenTodoClient

_UNIT_ALIASES = {
    "stk": "Stk", "stück": "Stk", "st": "Stk", "x": "Stk", "pcs": "Stk", "pc": "Stk", "piece": "Stk", "pieces": "Stk",
    "g": "g", "gr": "g", "gramm": "g",
    "kg": "kg", "kilo": "kg",
    "ml": "ml",
    "l": "l", "liter": "l", "ltr": "l",
    "pck": "Pck", "pk": "Pck", "packung": "Pck", "pack": "Pck", "p": "Pck", "pkg": "Pck", "packs": "Pck", "package": "Pck",
}

_QUICK_RE = re.compile(
    r"""^\s*
        (?:(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>[a-zA-ZäöüÄÖÜ]+)?\s+)?   # "2 " / "500 g " / "2x "
        (?P<name>.+?)
        (?:\s+(?P<qty2>\d+(?:[.,]\d+)?)\s*(?P<unit2>[a-zA-ZäöüÄÖÜ]+)?)?  # "Milch 2 l"
        \s*$""",
    re.VERBOSE,
)


@dataclass
class QuickItem:
    name: str
    qty: float | None
    unit: str | None


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    return _UNIT_ALIASES.get(u.lower())


def parse_quick(text: str) -> QuickItem:
    m = _QUICK_RE.match(text)
    if not m:
        return QuickItem(text.strip(), None, None)
    qty, unit, name = m.group("qty"), m.group("unit"), m.group("name")
    if qty is None and m.group("qty2"):
        qty, unit = m.group("qty2"), m.group("unit2")
    elif m.group("qty2"):
        # Zahl am Ende gehört zum Namen ("Cola Zero 2") wenn vorne schon eine steht
        name = f"{name} {m.group('qty2')}{m.group('unit2') or ''}".strip()
    # "2x Milch": Einheit "x" bedeutet Stück
    norm_unit = _norm_unit(unit)
    if unit and norm_unit is None:
        # unbekanntes Wort nach der Zahl ist Teil des Namens ("2 Bio Eier")
        name = f"{unit} {name}".strip()
    q = float(qty.replace(",", ".")) if qty else None
    return QuickItem(name.strip(), q, norm_unit)


class ShoppingList:
    def __init__(
        self,
        client: OpenTodoClient,
        db: Database,
        project_id: str | None = None,
        *,
        open_tasks_source: Callable[[], list[dict]] | None = None,
        on_write: Callable[[dict], None] | None = None,
    ):
        self.client = client
        self.db = db
        self.project_id = project_id or config.settings.project_id
        self._source = open_tasks_source
        self._on_write = on_write

    def _written(self, task: dict) -> dict:
        if self._on_write and task:
            self._on_write(task)
        return task

    # ------------------------------------------------------------ lesen
    def open_tasks(self) -> list[dict]:
        if self._source:
            return self._source()
        return self.client.tasks(self.project_id, open_only=True)

    def view(self, store: str | None = None) -> list[dict]:
        """Offene Liste, gruppiert nach Abschnitt in der Reihenfolge des Ladens.
        Im Laden: nur Einträge, die diesem Laden zugeordnet sind oder keinem."""
        tasks = self.open_tasks()
        order = [sec["id"] for sec in sections.all()]
        only: set[str] | None = None
        st = self.db.store_by_name(store)
        assign = self.db.task_stores()
        stores_by_id = {s["id"]: s["name"] for s in self.db.stores()}
        if st:
            custom = self.db.store_order(st["id"])
            if custom:
                order = custom
                only = set(custom)
            tasks = [t for t in tasks if not assign.get(t["id"]) or st["id"] in assign[t["id"]]]
        if only is not None:
            tasks = [t for t in tasks if not t.get("section_id") or t["section_id"] in only]
        rank = {sid: i for i, sid in enumerate(order)}
        tasks.sort(key=lambda t: (rank.get(t.get("section_id"), 99), t["title"].lower()))
        out = []
        for t in tasks:
            f = t.get("fields") or {}
            out.append(
                {
                    "id": t["id"],
                    "title": t["title"],
                    "qty": f.get(config.FIELD_MENGE),
                    "unit": f.get(config.FIELD_EINHEIT),
                    "price": f.get(config.FIELD_PREIS),
                    "section_id": t.get("section_id"),
                    "section": sections.by_id().get(t.get("section_id"), ""),
                    "labels": t.get("labels") or [],
                    "stores": [stores_by_id[i] for i in assign.get(t["id"], []) if i in stores_by_id],
                }
            )
        return out

    def history(self, days: int = 60) -> list[dict]:
        since = int((time.time() - days * 86400) * 1000)
        rows = self.client.tasks(self.project_id, completed_after_ms=since)
        rows = [t for t in rows if t.get("completed_at")]
        rows.sort(key=lambda t: t["completed_at"], reverse=True)
        seen, out = set(), []
        for t in rows:
            key = t["title"].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"title": t["title"], "completed_at": t["completed_at"], "section_id": t.get("section_id")})
        return out

    # ------------------------------------------------------------ schreiben
    def add(self, text: str, store: str | None = None) -> dict:
        """Artikel aus Schnellerfassung auf die Liste; offener Eintrag -> Menge addieren."""
        q = parse_quick(text)
        item = self.db.find_item(q.name)
        name = item["name"] if item else q.name
        qty = q.qty if q.qty is not None else (item["default_qty"] if item else None)
        unit = q.unit or (item["unit"] if item else None)
        section_id = (item["section_id"] if item else None) or sections.fallback_id()

        labels: list[str] = []
        st = self.db.store_by_name(store)

        existing = next(
            (t for t in self.open_tasks() if t["title"].lower() == name.lower()), None
        )
        if existing:
            f = existing.get("fields") or {}
            old = f.get(config.FIELD_MENGE)
            new_qty = (old or 0) + qty if qty is not None and (old is None or unit in (None, f.get(config.FIELD_EINHEIT))) else old
            changes: dict = {}
            fields: dict = {}
            if new_qty != old:
                fields[config.FIELD_MENGE] = new_qty
            if unit and not f.get(config.FIELD_EINHEIT):
                fields[config.FIELD_EINHEIT] = unit
            if fields:
                changes["fields"] = fields
            if st:
                self.db.add_task_store(existing["id"], st["id"])
            if item and not existing.get("section_id") and item.get("section_id"):
                changes["section_id"] = item["section_id"]
            return self._written(self.client.patch_task(existing["id"], **changes)) if changes else existing

        fields = {}
        if qty is not None and config.FIELD_MENGE:
            fields[config.FIELD_MENGE] = qty
        if unit and config.FIELD_EINHEIT:
            fields[config.FIELD_EINHEIT] = unit
        task = self._written(
            self.client.create_task(
                name, project_id=self.project_id, section_id=section_id, labels=labels, fields=fields
            )
        )
        if st:
            self.db.add_task_store(task["id"], st["id"])
        if not item:
            # neuen Artikel in den Stamm aufnehmen, damit er beim nächsten Mal bekannt ist
            self.db.upsert_item(name, default_qty=qty, unit=unit, section_id=section_id)
            task = dict(task) | {"_new_item": True}
        return task

    def check(self, task_id: str) -> dict:
        return self._written(self.client.complete_task(task_id))

    def uncheck(self, task_id: str) -> dict:
        return self._written(self.client.reopen_task(task_id))

    def set_qty(self, task_id: str, qty: float | None, unit: str | None = None) -> dict:
        fields: dict = {config.FIELD_MENGE: qty}
        if unit is not None:
            fields[config.FIELD_EINHEIT] = unit
        return self._written(self.client.patch_task(task_id, fields=fields))

    def move(self, task_id: str, section_name: str) -> dict:
        sid = sections.id_for(section_name)
        if not sid:
            raise ValueError(f"Unknown section: {section_name}")
        return self._written(self.client.patch_task(task_id, section_id=sid))

    def apply_template(self, name: str, store: str | None = None) -> list[dict]:
        out = []
        for it in self.db.template(name):
            qty = it["tqty"] if it["tqty"] is not None else it["default_qty"]
            unit = it["tunit"] or it["unit"] or ""
            text = f"{qty:g} {unit} {it['name']}".strip() if qty is not None else it["name"]
            out.append(self.add(text, store=store))
        return out
