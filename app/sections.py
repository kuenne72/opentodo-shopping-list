"""Abschnitte des Projekts „Einkauf" – live aus OpenTodo statt fest im Code.

`refresh(client)` holt die Abschnitte und hält sie in Reihenfolge ihrer Position.
Symbol und Farbe je Abschnitt liegen in der Dienst-Datenbank (section_meta);
für die acht Standardnamen gibt es Voreinstellungen.
"""

from __future__ import annotations

import threading

from . import config

# Default sections per language: (name, icon, color-key), in walking order.
DEFAULT_SECTIONS: dict[str, list[tuple[str, str, str]]] = {
    "de": [
        ("Obst/Gemüse", "apple", "green"),
        ("Brot/Backwaren", "bread", "ochre"),
        ("Kühlregal", "snow", "blue"),
        ("Fleisch/Fisch", "fish", "red"),
        ("Trockenware", "jar", "brown"),
        ("Getränke", "bottle", "teal"),
        ("Drogerie", "spray", "violet"),
        ("Sonstiges", "tag", "grey"),
    ],
    "en": [
        ("Produce", "apple", "green"),
        ("Bakery", "bread", "ochre"),
        ("Dairy & Chilled", "snow", "blue"),
        ("Meat & Fish", "fish", "red"),
        ("Pantry", "jar", "brown"),
        ("Drinks", "bottle", "teal"),
        ("Household & Drugstore", "spray", "violet"),
        ("Other", "tag", "grey"),
    ],
}
# name -> (icon, color-key) for all known default names
DEFAULT_META: dict[str, tuple[str, str]] = {
    n: (i, c) for rows in DEFAULT_SECTIONS.values() for n, i, c in rows
}
FALLBACK_NAMES = ("Sonstiges", "Other")
ICONS = ["apple", "carrot", "broccoli", "pepper", "mushroom", "bread", "snow", "cheese", "egg", "fish", "drumstick", "steak", "jar", "candy", "bottle", "coffee", "wine", "beer", "spray", "broom", "roll", "cross", "baby", "pet", "leaf", "plant", "watering", "tools", "hammer", "saw", "bulb", "plug", "paint", "tap", "plank", "box", "gift", "pencil", "car", "cart", "tag"]
COLORS = ["green", "ochre", "blue", "red", "brown", "teal", "violet", "grey", "pink", "orange"]

_lock = threading.Lock()
_sections: list[dict] = []   # filled by refresh()


def refresh(client, project_id: str | None = None) -> list[dict]:
    rows = client.sections(project_id or config.settings.project_id)
    rows.sort(key=lambda s: s.get("position") or 0)
    with _lock:
        _sections[:] = [{"id": s["id"], "name": s["name"], "position": s.get("position")} for s in rows]
    return all()


def all() -> list[dict]:
    with _lock:
        return [dict(s) for s in _sections]


def by_name() -> dict[str, str]:
    return {s["name"]: s["id"] for s in all()}


def by_id() -> dict[str, str]:
    return {s["id"]: s["name"] for s in all()}


def names() -> list[str]:
    return [s["name"] for s in all()]


def id_for(name: str) -> str | None:
    return by_name().get(name)


def fallback_id() -> str | None:
    """Abschnitt für unbekannte Artikel: „Sonstiges", sonst der letzte."""
    m = by_name()
    for n in FALLBACK_NAMES:
        if n in m:
            return m[n]
    rows = all()
    return rows[-1]["id"] if rows else None


def default_section_names(lang: str | None = None) -> list[str]:
    return [n for n, _, _ in DEFAULT_SECTIONS.get(lang or "de", DEFAULT_SECTIONS["de"])]


def default_meta(name: str) -> tuple[str, str]:
    return DEFAULT_META.get(name, ("tag", "grey"))
