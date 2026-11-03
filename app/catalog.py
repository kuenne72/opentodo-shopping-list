"""Read a catalog file (CSV, semicolon): name;section;unit;qty;aliases
(German headers name;abschnitt;einheit;menge;aliasse are accepted as well)."""

from __future__ import annotations

import csv
import os
from pathlib import Path

from . import config, sections

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
_HEADERS = {"section": ("section", "abschnitt"), "unit": ("unit", "einheit"), "qty": ("qty", "menge"), "aliases": ("aliases", "aliasse")}


def seed_path(lang: str | None = None) -> Path:
    """EINKAUF_SEED (explicit file) wins, else seed/items.<lang>.csv."""
    env = os.environ.get("EINKAUF_SEED")
    if env:
        return Path(env)
    lang = lang or config.settings.lang
    p = SEED_DIR / f"items.{lang}.csv"
    return p if p.exists() else SEED_DIR / "items.en.csv"


def _get(r: dict, key: str) -> str:
    for h in _HEADERS[key]:
        if r.get(h) is not None:
            return r[h].strip()
    return ""


def read_catalog(path: Path | str | None = None) -> list[dict]:
    rows: list[dict] = []
    with open(path or seed_path(), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            name = (r.get("name") or "").strip()
            if not name:
                continue
            unit = _get(r, "unit") or None
            qty = _get(r, "qty").replace(",", ".")
            rows.append({
                "name": name,
                "section_id": sections.id_for(_get(r, "section")),
                "unit": unit if unit in config.EINHEITEN else None,
                "default_qty": float(qty) if qty else None,
                "aliases": [a.strip() for a in _get(r, "aliases").split(",") if a.strip()],
            })
    return rows
