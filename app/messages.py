"""Messages the service sends to the UI (error texts). Language comes from the
`Accept-Language` header of the request (set by the UI), else EINKAUF_LANG."""

from __future__ import annotations

import contextvars

from . import config

current_lang: contextvars.ContextVar[str | None] = contextvars.ContextVar("lang", default=None)

MESSAGES: dict[str, dict[str, str]] = {
    "de": {
        "no_token": "Kein Token für {user}",
        "no_user": "Person fehlt (Header X-Einkauf-User)",
        "unknown_section": "Unbekannter Abschnitt",
        "unknown_store": "Unbekannter Laden: {names}",
        "section_exists": "Abschnitt gibt es schon",
        "section_missing": "Abschnitt unbekannt",
        "hint_401": "Token ungültig oder ohne Schreibrecht",
        "hint_403": "keine Berechtigung – das Projekt {project} muss für diese Person als Bearbeiter freigegeben sein",
        "token_rejected": "Token abgelehnt: HTTP {status}",
        "project_invisible": "{name} sieht das Projekt {project} nicht: Einladung in OpenTodo annehmen bzw. als Bearbeiter freigeben, dann Token erneut speichern.",
        "scope_low": "Token hat nur Zugriff „{scope}“; es wird „Voll“ benötigt.",
    },
    "en": {
        "no_token": "No token stored for {user}",
        "no_user": "Person missing (header X-Einkauf-User)",
        "unknown_section": "Unknown section",
        "unknown_store": "Unknown store: {names}",
        "section_exists": "A section with this name already exists",
        "section_missing": "Section not found",
        "hint_401": "Token invalid or without write access",
        "hint_403": "no permission – project {project} must be shared with this person as editor",
        "token_rejected": "Token rejected: HTTP {status}",
        "project_invisible": "{name} cannot see project {project}: accept the invitation in OpenTodo or share it as editor, then save the token again.",
        "scope_low": "Token only has access “{scope}”; “Full” is required.",
    },
}


def lang_from_header(value: str | None) -> str | None:
    if not value:
        return None
    code = value.split(",")[0].strip()[:2].lower()
    return code if code in MESSAGES else None


def msg(key: str, **vars) -> str:
    lang = current_lang.get() or config.settings.lang
    table = MESSAGES.get(lang) or MESSAGES["en"]
    return (table.get(key) or MESSAGES["en"][key]).format(**vars)
