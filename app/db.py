"""SQLite-Ablage des Begleitdienstes (Plan 3.3, 3.4).

Tabellen:
  items      Artikelstamm: Name, Aliasse, Standardmenge, Einheit, Abschnitt
  stores     Läden (= OpenTodo-Label)
  store_order Reihenfolge der Abschnitte je Laden
  templates  Vorlagen mit Positionen
  users      Personen mit verschlüsseltem OpenTodo-Token
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    aliases TEXT NOT NULL DEFAULT '[]',
    default_qty REAL,
    unit TEXT,
    section_id TEXT
);
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    label_id TEXT
);
CREATE TABLE IF NOT EXISTS store_order (
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    section_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (store_id, section_id)
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS template_items (
    template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    qty REAL,
    unit TEXT,
    PRIMARY KEY (template_id, item_id)
);
CREATE TABLE IF NOT EXISTS task_stores (
    task_id TEXT NOT NULL,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, store_id)
);
CREATE TABLE IF NOT EXISTS section_meta (
    section_id TEXT PRIMARY KEY,
    icon TEXT,
    color TEXT
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    token_enc BLOB NOT NULL,
    pin_hash TEXT
);
"""


class Database:
    def __init__(self, path: Path, secret: str = ""):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fernet = Fernet(secret.encode()) if secret else None
        with self.connect() as c:
            c.executescript(SCHEMA)
            cols = [r["name"] for r in c.execute("PRAGMA table_info(stores)")]
            if "position" not in cols:
                c.execute("ALTER TABLE stores ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
                c.execute("UPDATE stores SET position = id")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ------------------------------------------------------------ items
    def upsert_item(
        self,
        name: str,
        *,
        aliases: list[str] | None = None,
        default_qty: float | None = None,
        unit: str | None = None,
        section_id: str | None = None,
    ) -> int:
        with self.connect() as c:
            c.execute(
                """INSERT INTO items (name, aliases, default_qty, unit, section_id)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     aliases=excluded.aliases,
                     default_qty=COALESCE(excluded.default_qty, items.default_qty),
                     unit=COALESCE(excluded.unit, items.unit),
                     section_id=COALESCE(excluded.section_id, items.section_id)""",
                (name, json.dumps(aliases or []), default_qty, unit, section_id),
            )
            row = c.execute("SELECT id FROM items WHERE name = ?", (name,)).fetchone()
            return int(row["id"])

    def items(self) -> list[dict]:
        with self.connect() as c:
            rows = c.execute("SELECT * FROM items ORDER BY name").fetchall()
        return [dict(r) | {"aliases": json.loads(r["aliases"])} for r in rows]

    def find_item(self, text: str) -> dict | None:
        key = text.strip().lower()
        for it in self.items():
            names = [it["name"].lower()] + [a.lower() for a in it["aliases"]]
            if key in names:
                return it
        return None

    # ------------------------------------------------------------ stores
    def upsert_store(self, name: str, label_id: str | None = None) -> int:
        with self.connect() as c:
            nxt = (c.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM stores").fetchone()[0])
            c.execute(
                """INSERT INTO stores (name, label_id, position) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET label_id=COALESCE(excluded.label_id, stores.label_id)""",
                (name, label_id, nxt),
            )
            return int(c.execute("SELECT id FROM stores WHERE name = ?", (name,)).fetchone()["id"])

    def stores(self) -> list[dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM stores ORDER BY position, name")]

    def set_stores_order(self, names: list[str]) -> None:
        with self.connect() as c:
            for i, n in enumerate(names):
                c.execute("UPDATE stores SET position = ? WHERE lower(name) = lower(?)", (i, n))

    def set_store_order(self, store_id: int, section_ids: list[str]) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM store_order WHERE store_id = ?", (store_id,))
            c.executemany(
                "INSERT INTO store_order (store_id, section_id, position) VALUES (?, ?, ?)",
                [(store_id, sid, i) for i, sid in enumerate(section_ids)],
            )

    def store_order(self, store_id: int) -> list[str]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT section_id FROM store_order WHERE store_id = ? ORDER BY position",
                (store_id,),
            ).fetchall()
        return [r["section_id"] for r in rows]

    # ------------------------------------------------------------ templates
    def upsert_template(self, name: str, positions: list[tuple[int, float | None, str | None]]) -> int:
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO templates (name) VALUES (?)", (name,))
            tid = int(c.execute("SELECT id FROM templates WHERE name = ?", (name,)).fetchone()["id"])
            c.execute("DELETE FROM template_items WHERE template_id = ?", (tid,))
            c.executemany(
                "INSERT INTO template_items (template_id, item_id, qty, unit) VALUES (?, ?, ?, ?)",
                [(tid, iid, qty, unit) for iid, qty, unit in positions],
            )
            return tid

    def template(self, name: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute(
                """SELECT i.*, ti.qty AS tqty, ti.unit AS tunit
                   FROM templates t
                   JOIN template_items ti ON ti.template_id = t.id
                   JOIN items i ON i.id = ti.item_id
                   WHERE t.name = ?""",
                (name,),
            ).fetchall()
        return [dict(r) | {"aliases": json.loads(r["aliases"])} for r in rows]

    def templates(self) -> list[str]:
        with self.connect() as c:
            return [r["name"] for r in c.execute("SELECT name FROM templates ORDER BY name")]

    # ------------------------------------------------------------ users
    def set_user_token(self, name: str, token: str, pin_hash: str | None = None) -> None:
        if not self._fernet:
            raise RuntimeError("EINKAUF_SECRET fehlt; Token können nicht abgelegt werden")
        enc = self._fernet.encrypt(token.encode())
        with self.connect() as c:
            c.execute(
                """INSERT INTO users (name, token_enc, pin_hash) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET token_enc=excluded.token_enc,
                     pin_hash=COALESCE(excluded.pin_hash, users.pin_hash)""",
                (name, enc, pin_hash),
            )

    def user_token(self, name: str) -> str | None:
        if not self._fernet:
            return None
        with self.connect() as c:
            row = c.execute("SELECT token_enc FROM users WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        try:
            return self._fernet.decrypt(bytes(row["token_enc"])).decode()
        except InvalidToken:
            return None

    def users(self) -> list[str]:
        with self.connect() as c:
            return [r["name"] for r in c.execute("SELECT name FROM users ORDER BY name")]

    # ------------------------------------------------------------ löschen (Phase 3)
    def delete_item(self, item_id: int) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM items WHERE id = ?", (item_id,))

    def delete_store(self, store_id: int) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM stores WHERE id = ?", (store_id,))

    def delete_template(self, name: str) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM templates WHERE name = ?", (name,))

    def delete_user(self, name: str) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM users WHERE name = ?", (name,))

    def update_item(self, item_id: int, **values) -> None:
        allowed = {"name", "aliases", "default_qty", "unit", "section_id"}
        cols = {k: v for k, v in values.items() if k in allowed}
        if "aliases" in cols:
            cols["aliases"] = json.dumps(cols["aliases"] or [])
        if not cols:
            return
        sets = ", ".join(f"{k} = ?" for k in cols)
        with self.connect() as c:
            c.execute(f"UPDATE items SET {sets} WHERE id = ?", (*cols.values(), item_id))

    def template_detail(self, name: str) -> list[dict]:
        with self.connect() as c:
            rows = c.execute(
                """SELECT i.id AS item_id, i.name, ti.qty, ti.unit
                   FROM templates t JOIN template_items ti ON ti.template_id = t.id
                   JOIN items i ON i.id = ti.item_id WHERE t.name = ? ORDER BY i.name""",
                (name,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ Katalog-Import
    def import_catalog(self, rows: list[dict], *, overwrite: bool = False) -> dict:
        """rows: [{name, section_id, unit, default_qty, aliases}]. Bestehende Artikel
        werden nur ergänzt (fehlende Werte), bei overwrite=True ersetzt."""
        added = updated = 0
        existing = {i["name"].lower(): i for i in self.items()}
        with self.connect() as c:
            for r in rows:
                key = r["name"].lower()
                if key in existing:
                    cur = existing[key]
                    if overwrite:
                        vals = (json.dumps(r.get("aliases") or []), r.get("default_qty"), r.get("unit"), r.get("section_id"), cur["id"])
                    else:
                        merged_alias = sorted(set(cur["aliases"]) | set(r.get("aliases") or []))
                        vals = (json.dumps(merged_alias),
                                cur["default_qty"] if cur["default_qty"] is not None else r.get("default_qty"),
                                cur["unit"] or r.get("unit"),
                                cur["section_id"] or r.get("section_id"), cur["id"])
                    c.execute("UPDATE items SET aliases=?, default_qty=?, unit=?, section_id=? WHERE id=?", vals)
                    updated += 1
                else:
                    c.execute("INSERT INTO items (name, aliases, default_qty, unit, section_id) VALUES (?,?,?,?,?)",
                              (r["name"], json.dumps(r.get("aliases") or []), r.get("default_qty"), r.get("unit"), r.get("section_id")))
                    added += 1
        return {"added": added, "updated": updated}


    # ------------------------------------------------------------ Abschnitts-Metadaten
    def section_meta(self) -> dict[str, dict]:
        with self.connect() as c:
            return {r["section_id"]: {"icon": r["icon"], "color": r["color"]} for r in c.execute("SELECT * FROM section_meta")}

    def set_section_meta(self, section_id: str, icon: str | None, color: str | None) -> None:
        with self.connect() as c:
            c.execute("""INSERT INTO section_meta (section_id, icon, color) VALUES (?,?,?)
                         ON CONFLICT(section_id) DO UPDATE SET icon=COALESCE(excluded.icon, section_meta.icon),
                                                              color=COALESCE(excluded.color, section_meta.color)""",
                      (section_id, icon, color))


    # ------------------------------------------------------------ Laden je Eintrag (Dienst-intern, kein OpenTodo-Label)
    def task_stores(self) -> dict[str, list[int]]:
        out: dict[str, list[int]] = {}
        with self.connect() as c:
            for r in c.execute("SELECT task_id, store_id FROM task_stores"):
                out.setdefault(r["task_id"], []).append(int(r["store_id"]))
        return out

    def set_task_stores(self, task_id: str, store_ids: list[int]) -> None:
        with self.connect() as c:
            c.execute("DELETE FROM task_stores WHERE task_id = ?", (task_id,))
            c.executemany("INSERT INTO task_stores (task_id, store_id) VALUES (?, ?)", [(task_id, i) for i in store_ids])

    def add_task_store(self, task_id: str, store_id: int) -> None:
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO task_stores (task_id, store_id) VALUES (?, ?)", (task_id, store_id))

    def store_by_name(self, name: str | None) -> dict | None:
        if not name:
            return None
        return next((s for s in self.stores() if s["name"].lower() == name.lower()), None)
