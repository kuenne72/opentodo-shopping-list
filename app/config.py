"""Configuration from environment variables.

Nothing instance-specific is hard-coded: the project and its custom fields are
looked up in OpenTodo by name at start-up (see `app/bootstrap.py`). The IDs are
stored in the module variables below once they have been resolved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Custom-field IDs of the shopping project; filled in by bootstrap.resolve().
FIELD_MENGE = ""     # quantity
FIELD_EINHEIT = ""   # unit
FIELD_PREIS = ""     # price

EINHEITEN = ("Stk", "g", "kg", "ml", "l", "Pck")


@dataclass
class Settings:
    opentodo_url: str = field(
        default_factory=lambda: os.environ.get("OPENTODO_URL", "").rstrip("/")
    )
    db_path: Path = field(
        default_factory=lambda: Path(os.environ.get("EINKAUF_DB", "data/einkauf.db"))
    )
    secret: str = field(default_factory=lambda: os.environ.get("EINKAUF_SECRET", ""))
    # Either set the ID directly or let the service find the project by name.
    project_id: str = field(default_factory=lambda: os.environ.get("EINKAUF_PROJECT_ID", ""))
    project_name: str = field(
        default_factory=lambda: os.environ.get("EINKAUF_PROJECT_NAME", "Einkauf")
    )
    poll_seconds: int = field(
        default_factory=lambda: int(os.environ.get("EINKAUF_POLL_SECONDS", "300"))
    )
    lang: str = field(default_factory=lambda: os.environ.get("EINKAUF_LANG", "de"))


settings = Settings()


def require_url() -> str:
    if not settings.opentodo_url:
        raise SystemExit(
            "OPENTODO_URL is not set. Put the address of your OpenTodo instance into .env, "
            "e.g. OPENTODO_URL=https://opentodo.example.net"
        )
    return settings.opentodo_url
