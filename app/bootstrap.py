"""Find the shopping project and its custom fields in OpenTodo by name.

`resolve(client)` sets `config.settings.project_id` and `config.FIELD_*`.
`setup(client, lang)` additionally creates the default sections if the project
has none. The project and the three custom fields have to exist already
(create them once in OpenTodo, see README).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config, sections

# accepted field names (case-insensitive) -> config attribute
FIELD_NAMES = {
    "FIELD_MENGE": ("menge", "quantity", "qty", "amount"),
    "FIELD_EINHEIT": ("einheit", "unit"),
    "FIELD_PREIS": ("preis", "price"),
}


@dataclass
class Report:
    project: dict | None = None
    fields: dict[str, bool] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def resolve(client) -> Report:
    rep = Report()
    projects = client.projects()
    pid = config.settings.project_id
    if pid:
        rep.project = next((p for p in projects if p["id"] == pid), None)
        if not rep.project:
            rep.problems.append(
                f"Project {pid} (EINKAUF_PROJECT_ID) is not visible for this account: accept the invitation / share the project."
            )
    else:
        wanted = config.settings.project_name.strip().lower()
        hits = [p for p in projects if (p.get("name") or "").strip().lower() == wanted and not p.get("deleted_at")]
        if len(hits) == 1:
            rep.project = hits[0]
            config.settings.project_id = hits[0]["id"]
        elif len(hits) > 1:
            rep.problems.append(
                f"Several projects are named '{config.settings.project_name}'. Set EINKAUF_PROJECT_ID to pick one."
            )
        else:
            rep.problems.append(
                f"No project named '{config.settings.project_name}' found. Create it in OpenTodo or set EINKAUF_PROJECT_NAME / EINKAUF_PROJECT_ID."
            )
    if not rep.project:
        return rep

    flds = client.fields(rep.project["id"])
    for attr, names in FIELD_NAMES.items():
        hit = next((f for f in flds if (f.get("name") or "").strip().lower() in names), None)
        rep.fields[attr] = bool(hit)
        if hit:
            setattr(config, attr, hit["id"])
        elif attr != "FIELD_PREIS":   # price is optional
            rep.problems.append(
                f"Custom field missing in project '{rep.project['name']}': one of {', '.join(names)}."
            )
    return rep


def setup(client, lang: str | None = None) -> tuple[Report, list[str]]:
    """resolve() and create default sections if the project has none."""
    rep = resolve(client)
    created: list[str] = []
    if rep.project:
        existing = client.sections(rep.project["id"])
        if not existing:
            for i, name in enumerate(sections.default_section_names(lang or config.settings.lang)):
                client.create_section(name, rep.project["id"], position=i)
                created.append(name)
        sections.refresh(client)
    return rep, created
