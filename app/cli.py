"""Kommandozeile für Phase 1.

  einkauf check                  API-Verbindung und Schreibtest (legt Aufgabe "Testartikel" an und löscht sie wieder)
  einkauf setup [--sprache de|en]  Projekt/Felder suchen, Standardabschnitte anlegen
  einkauf list [--laden Edeka]   offene Liste
  einkauf add "2 l Milch" [--laden Edeka]
  einkauf done <task-id>
  einkauf history
  einkauf item set "Milch" --menge 1 --einheit l --abschnitt Kühlregal --alias Vollmilch
  einkauf item list
  einkauf store set Edeka --label-id <id> --reihenfolge "Obst/Gemüse,Brot/Backwaren,..."
  einkauf template set Wochenende "Milch:2:l,Brot,Eier:10:Stk"
  einkauf template apply Wochenende [--laden Edeka]
  einkauf user set Anna            ask for the token (hidden) and store it encrypted

Token: Umgebungsvariable OPENTODO_TOKEN oder --user <Name> (aus der DB).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time

from . import bootstrap, config, sections
from .core import ShoppingList
from .db import Database
from .opentodo_client import OpenTodoClient, OpenTodoError


def _db() -> Database:
    return Database(config.settings.db_path, config.settings.secret)


def _client(db: Database, user: str | None) -> OpenTodoClient:
    token = os.environ.get("OPENTODO_TOKEN")
    if user:
        token = db.user_token(user)
        if not token:
            sys.exit(f"Kein Token für {user} abgelegt (einkauf user set {user}).")
    if not token:
        token = getpass.getpass("OpenTodo-Token: ")
    c = OpenTodoClient(config.require_url(), token)
    try:
        for problem in bootstrap.resolve(c).problems:
            print(f"Hinweis: {problem}", file=sys.stderr)
        sections.refresh(c)
    except OpenTodoError:
        pass
    return c


def cmd_check(args, db):
    c = _client(db, args.user)
    me = c.me()
    print(f"Verbunden als {me['user']['name']} ({me['auth']['scope']}), Rolle {me['user']['role']}")
    rep = bootstrap.resolve(c)
    if not rep.project:
        sys.exit("\n".join(rep.problems))
    print(f"Projekt: {rep.project['name']} ({rep.project['id']})")
    print(f"Abschnitte: {', '.join(sections.names()) or '(keine – `einkauf setup` legt Standardabschnitte an)'}")
    for attr, label in (("FIELD_MENGE", "Menge"), ("FIELD_EINHEIT", "Einheit"), ("FIELD_PREIS", "Preis (optional)")):
        print(f"Feld {label}: {'ok' if rep.fields.get(attr) else 'FEHLT'}")
    if not rep.ok:
        sys.exit("\n".join(rep.problems))
    # Schreibtest
    t = c.create_task(
        "Testartikel (einkauf check)",
        project_id=config.settings.project_id,
        section_id=sections.fallback_id(),
        fields={config.FIELD_MENGE: 3, config.FIELD_EINHEIT: "Stk"},
    )
    f = t.get("fields") or {}
    print(f"POST ok: id={t['id']} Menge={f.get(config.FIELD_MENGE)} Einheit={f.get(config.FIELD_EINHEIT)} Abschnitt={sections.by_id().get(t.get('section_id'))}")
    t = c.patch_task(t["id"], fields={config.FIELD_MENGE: 5}, section_id=sections.all()[0]["id"])
    f = t.get("fields") or {}
    print(f"PATCH ok: Menge={f.get(config.FIELD_MENGE)} Einheit={f.get(config.FIELD_EINHEIT)} Abschnitt={sections.by_id().get(t.get('section_id'))}")
    t = c.complete_task(t["id"])
    print(f"Abschluss ok: completed_at={t.get('completed_at')}")
    t = c.reopen_task(t["id"])
    print(f"Wiedereröffnen ok: completed_at={t.get('completed_at')}")
    c.patch_task(t["id"], deleted_at=int(time.time() * 1000))
    print("Testaufgabe in den Papierkorb verschoben.")


def cmd_setup(args, db):
    c = _client(db, args.user)
    rep, created = bootstrap.setup(c, args.sprache)
    if rep.project:
        print(f"Projekt: {rep.project['name']} ({rep.project['id']})")
    if created:
        print("Abschnitte angelegt: " + ", ".join(created))
    for attr, label in (("FIELD_MENGE", "Menge"), ("FIELD_EINHEIT", "Einheit"), ("FIELD_PREIS", "Preis (optional)")):
        print(f"Feld {label}: {'ok' if rep.fields.get(attr) else 'FEHLT'}")
    if rep.problems:
        sys.exit("\n".join(rep.problems))
    print("Bereit. Als Nächstes: einkauf user set <Name> und einkauf item import")


def cmd_list(args, db):
    sl = ShoppingList(_client(db, args.user), db)
    rows = sl.view(args.laden)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    cur = None
    for r in rows:
        if r["section"] != cur:
            cur = r["section"]
            print(f"\n[{cur or 'ohne Abschnitt'}]")
        q = f"{r['qty']:g} {r['unit'] or ''}".strip() if r["qty"] is not None else ""
        print(f"  {r['id'][:8]}  {q:>8}  {r['title']}")


def cmd_add(args, db):
    sl = ShoppingList(_client(db, args.user), db)
    t = sl.add(args.text, store=args.laden)
    f = t.get("fields") or {}
    print(f"{t['title']}: Menge={f.get(config.FIELD_MENGE)} Einheit={f.get(config.FIELD_EINHEIT)} Abschnitt={sections.by_id().get(t.get('section_id'))}")


def cmd_done(args, db):
    sl = ShoppingList(_client(db, args.user), db)
    tid = args.task_id
    if len(tid) < 36:
        match = [t for t in sl.open_tasks() if t["id"].startswith(tid)]
        if len(match) != 1:
            sys.exit(f"{len(match)} Treffer für {tid}")
        tid = match[0]["id"]
    sl.check(tid)
    print("erledigt")


def cmd_history(args, db):
    sl = ShoppingList(_client(db, args.user), db)
    for r in sl.history(args.tage):
        print(f"{time.strftime('%d.%m.', time.localtime(r['completed_at']/1000))}  {r['title']}")


def cmd_item(args, db):
    if args.item_cmd == "import":
        from .catalog import read_catalog
        rows = read_catalog(args.datei)
        r = db.import_catalog(rows, overwrite=args.ersetzen)
        print(f"{r['added']} neu, {r['updated']} vorhanden" + (" (ersetzt)" if args.ersetzen else " (ergänzt)"))
        return
    if args.item_cmd == "list":
        for it in db.items():
            print(f"{it['name']:<25} {it['default_qty'] or '':>5} {it['unit'] or '':<4} {sections.by_id().get(it['section_id'], ''):<15} {', '.join(it['aliases'])}")
        return
    sid = sections.id_for(args.abschnitt) if args.abschnitt else None
    if args.abschnitt and not sid:
        sys.exit(f"Unbekannter Abschnitt: {args.abschnitt}. Bekannt: {', '.join(sections.names())}")
    db.upsert_item(args.name, aliases=args.alias or [], default_qty=args.menge, unit=args.einheit, section_id=sid)
    print("gespeichert")


def cmd_store(args, db):
    if args.store_cmd == "list":
        for s in db.stores():
            order = [sections.by_id().get(x, x) for x in db.store_order(s["id"])]
            print(f"{s['name']:<12} label={s['label_id']}  Reihenfolge: {', '.join(order) or '(Standard)'}")
        return
    sid = db.upsert_store(args.name, args.label_id)
    if args.reihenfolge:
        names = [n.strip() for n in args.reihenfolge.split(",") if n.strip()]
        m = sections.by_name()
        db.set_store_order(sid, [m[n] for n in names if n in m])
    print("gespeichert")


def cmd_template(args, db):
    if args.template_cmd == "list":
        for n in db.templates():
            print(n, "->", ", ".join(it["name"] for it in db.template(n)))
        return
    if args.template_cmd == "apply":
        sl = ShoppingList(_client(db, args.user), db)
        for t in sl.apply_template(args.name, store=args.laden):
            print(" +", t["title"])
        return
    positions = []
    for part in args.spec.split(","):
        bits = [b.strip() for b in part.split(":")]
        it = db.find_item(bits[0])
        if not it:
            iid = db.upsert_item(bits[0])
        else:
            iid = it["id"]
        qty = float(bits[1].replace(",", ".")) if len(bits) > 1 and bits[1] else None
        unit = bits[2] if len(bits) > 2 and bits[2] else None
        positions.append((iid, qty, unit))
    db.upsert_template(args.name, positions)
    print("gespeichert")


def cmd_user(args, db):
    if args.user_cmd == "list":
        print("\n".join(db.users()))
        return
    token = getpass.getpass(f"OpenTodo-Token für {args.name}: ").strip()
    if not token:
        sys.exit("Kein Token eingegeben.")
    try:
        me = OpenTodoClient(config.require_url(), token).me()
    except OpenTodoError as e:
        sys.exit(f"Token abgelehnt (HTTP {e.status}); nichts gespeichert.")
    db.set_user_token(args.name, token)
    print(f"abgelegt – verbunden als {me['user']['name']} ({me['auth']['scope']})")


def main(argv=None):
    p = argparse.ArgumentParser(prog="einkauf")
    p.add_argument("--user", help="Person, deren Token aus der DB verwendet wird")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check")
    s = sub.add_parser("setup"); s.add_argument("--sprache", choices=("de", "en"), default=None)
    s = sub.add_parser("list"); s.add_argument("--laden"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("add"); s.add_argument("text"); s.add_argument("--laden")
    s = sub.add_parser("done"); s.add_argument("task_id")
    s = sub.add_parser("history"); s.add_argument("--tage", type=int, default=60)

    s = sub.add_parser("item"); ss = s.add_subparsers(dest="item_cmd", required=True)
    ss.add_parser("list")
    x = ss.add_parser("import"); x.add_argument("datei", nargs="?"); x.add_argument("--ersetzen", action="store_true")
    x = ss.add_parser("set"); x.add_argument("name"); x.add_argument("--menge", type=float)
    x.add_argument("--einheit", choices=config.EINHEITEN); x.add_argument("--abschnitt")
    x.add_argument("--alias", action="append")

    s = sub.add_parser("store"); ss = s.add_subparsers(dest="store_cmd", required=True)
    ss.add_parser("list")
    x = ss.add_parser("set"); x.add_argument("name"); x.add_argument("--label-id"); x.add_argument("--reihenfolge")

    s = sub.add_parser("template"); ss = s.add_subparsers(dest="template_cmd", required=True)
    ss.add_parser("list")
    x = ss.add_parser("set"); x.add_argument("name"); x.add_argument("spec")
    x = ss.add_parser("apply"); x.add_argument("name"); x.add_argument("--laden")

    s = sub.add_parser("user"); ss = s.add_subparsers(dest="user_cmd", required=True)
    ss.add_parser("list")
    x = ss.add_parser("set"); x.add_argument("name")

    args = p.parse_args(argv)
    db = _db()
    try:
        {
            "check": cmd_check, "setup": cmd_setup, "list": cmd_list, "add": cmd_add, "done": cmd_done,
            "history": cmd_history, "item": cmd_item, "store": cmd_store,
            "template": cmd_template, "user": cmd_user,
        }[args.cmd](args, db)
    except OpenTodoError as e:
        sys.exit(f"OpenTodo-Fehler: {e}")


if __name__ == "__main__":
    main()
