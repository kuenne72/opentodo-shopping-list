"""HTTP-Dienst (Phase 2): Webhook-Empfang, Cache, SSE, JSON-API.

Start:  uvicorn app.server:app --host 0.0.0.0 --port 8086
Env:    EINKAUF_SECRET          Fernet-Schlüssel für Token in der DB
        EINKAUF_WEBHOOK_SECRET  whsec_… des OpenTodo-Webhooks
        EINKAUF_SYNC_USER       Person, deren Token für Vollabgleich/Poll genutzt wird
        EINKAUF_POLL_SECONDS    Poll-Intervall (Fallback), Standard 300

Personenbindung je Anfrage: Header X-Einkauf-User: <Name> (oder Query ?user=).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import bootstrap, config, sections
from .messages import current_lang, lang_from_header, msg
from .cache import ListCache
from .core import ShoppingList
from .db import Database
from .opentodo_client import OpenTodoClient, OpenTodoError
from .webhook import verify

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("einkauf")

WEBHOOK_SECRET = os.environ.get("EINKAUF_WEBHOOK_SECRET", "")
SYNC_USER = os.environ.get("EINKAUF_SYNC_USER", "")

db = Database(config.settings.db_path, config.settings.secret)
cache = ListCache(config.settings.project_id or "")
_clients: dict[str, OpenTodoClient] = {}


def _client_for(user: str) -> OpenTodoClient:
    if user not in _clients:
        token = db.user_token(user)
        if not token:
            raise HTTPException(401, msg("no_token", user=user))
        _clients[user] = OpenTodoClient(config.require_url(), token)
    return _clients[user]


def _list_for(user: str) -> ShoppingList:
    return ShoppingList(
        _client_for(user),
        db,
        open_tasks_source=lambda: cache.tasks(open_only=True),
        on_write=cache.upsert_local,
    )


def _sync_user() -> str | None:
    if SYNC_USER:
        return SYNC_USER
    users = db.users()
    return users[0] if users else None


def full_sync() -> int:
    user = _sync_user()
    if not user:
        log.warning("No user with a token; full sync skipped")
        return 0
    c = _client_for(user)
    if not config.settings.project_id or not config.FIELD_MENGE:
        rep = bootstrap.resolve(c)
        for pr in rep.problems:
            log.error("Setup: %s", pr)
        cache.project_id = config.settings.project_id
        if not rep.project:
            return 0
    try:
        sections.refresh(c)
    except OpenTodoError as e:
        log.warning("Sections not loaded: %s", e)
    rows = c.tasks(config.settings.project_id)
    cache.replace_all(rows)
    return len(rows)


async def _poll_loop():
    while True:
        await asyncio.sleep(config.settings.poll_seconds)
        try:
            n = await asyncio.to_thread(full_sync)
            log.info("Poll: %d tasks", n)
        except Exception as e:  # noqa: BLE001
            log.warning("Poll failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache.bind_loop(asyncio.get_running_loop())
    if not config.settings.opentodo_url:
        log.error("OPENTODO_URL is not set – the service cannot reach OpenTodo")
    try:
        n = await asyncio.to_thread(full_sync)
        log.info("Start: %d tasks loaded", n)
    except Exception as e:  # noqa: BLE001
        log.warning("Start without full sync: %s", e)
    task = asyncio.create_task(_poll_loop())
    yield
    task.cancel()


app = FastAPI(title="einkauf", lifespan=lifespan)


@app.middleware("http")
async def _lang_middleware(request: Request, call_next):
    token = current_lang.set(lang_from_header(request.headers.get("accept-language")))
    try:
        return await call_next(request)
    finally:
        current_lang.reset(token)


@app.exception_handler(OpenTodoError)
async def _ot_error(request: Request, e: OpenTodoError):
    who = request.headers.get("X-Einkauf-User") or request.query_params.get("user") or "-"
    log.warning("OpenTodo %s bei %s (Person %s): %s", e.status, e.path, who, e.body)
    hint = {401: msg("hint_401"), 403: msg("hint_403", project=config.settings.project_name)}.get(e.status, "")
    return JSONResponse({"error": "opentodo", "status": e.status, "detail": e.body, "hint": hint}, status_code=502)


# ---------------------------------------------------------------- Webhook
@app.post("/webhook")
async def webhook(request: Request):
    raw = await request.body()
    ts = request.headers.get("X-OpenTodo-Timestamp")
    sig = request.headers.get("X-OpenTodo-Signature")
    if not verify(WEBHOOK_SECRET, ts, raw, sig):
        raise HTTPException(401, "bad signature")
    payload = json.loads(raw)
    event = payload.get("event", "")
    if event == "ping":
        return {"ok": True, "ping": True}
    task = (payload.get("data") or {}).get("task")
    applied = cache.apply_event(payload.get("id", ""), event, task)
    return {"ok": True, "applied": applied}


# ---------------------------------------------------------------- SSE
@app.get("/events")
async def events():
    q = cache.subscribe()

    async def gen():
        try:
            yield f"event: hello\ndata: {json.dumps({'version': cache.version})}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            cache.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------- API
def _user(x_einkauf_user: str | None, user: str | None) -> str:
    u = x_einkauf_user or user
    if not u:
        raise HTTPException(400, msg("no_user"))
    return u


@app.get("/api/status")
def status():
    return {
        "version": cache.version,
        "open": len(cache.tasks()),
        "last_full_sync": cache.last_full_sync,
        "users": db.users(),
        "stores": [s["name"] for s in db.stores()],
        "templates": db.templates(),
        "sections": sections.names(),
        "section_ids": sections.by_name(),
        "units": list(config.EINHEITEN),
        "project_ok": bool(config.settings.project_id and config.FIELD_MENGE and config.FIELD_EINHEIT),
        "lang": config.settings.lang,
        "project_name": config.settings.project_name,
    }


@app.get("/api/list")
def api_list(laden: str | None = None, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return {"version": cache.version, "items": _list_for(_user(x_einkauf_user, user)).view(laden)}


class AddBody(BaseModel):
    text: str
    laden: str | None = None


@app.post("/api/add")
def api_add(body: AddBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).add(body.text, store=body.laden)


@app.post("/api/check/{task_id}")
def api_check(task_id: str, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).check(task_id)


@app.post("/api/uncheck/{task_id}")
def api_uncheck(task_id: str, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).uncheck(task_id)


class QtyBody(BaseModel):
    qty: float | None
    unit: str | None = None


@app.post("/api/qty/{task_id}")
def api_qty(task_id: str, body: QtyBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).set_qty(task_id, body.qty, body.unit)


class MoveBody(BaseModel):
    section: str


@app.post("/api/move/{task_id}")
def api_move(task_id: str, body: MoveBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    if not sections.id_for(body.section):
        raise HTTPException(400, msg("unknown_section"))
    return _list_for(_user(x_einkauf_user, user)).move(task_id, body.section)


class StoresBody(BaseModel):
    stores: list[str]            # Ladennamen; leer = kein Laden


@app.post("/api/task-stores/{task_id}")
def api_task_stores(task_id: str, body: StoresBody):
    """Läden eines Eintrags setzen (Dienst-intern; kein OpenTodo-Label nötig)."""
    by_name = {s["name"].lower(): s["id"] for s in db.stores()}
    missing = [n for n in body.stores if n.lower() not in by_name]
    if missing:
        raise HTTPException(400, msg("unknown_store", names=", ".join(missing)))
    db.set_task_stores(task_id, [by_name[n.lower()] for n in body.stores])
    cache.version += 1
    return {"ok": True, "stores": body.stores}


@app.get("/api/history")
def api_history(tage: int = 60, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).history(tage)


class TemplateApply(BaseModel):
    laden: str | None = None


@app.post("/api/template/{name}/apply")
def api_template_apply(name: str, body: TemplateApply, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _list_for(_user(x_einkauf_user, user)).apply_template(name, store=body.laden)


@app.post("/api/sync")
def api_sync():
    return {"loaded": full_sync(), "version": cache.version, "at": time.time()}


@app.get("/api/items")
def api_items():
    return db.items()


# ================================================================ Phase 3: Stammdaten-API + Oberfläche
from pathlib import Path  # noqa: E402

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

STATIC = Path(__file__).parent / "static"


class ItemBody(BaseModel):
    name: str
    aliases: list[str] = []
    default_qty: float | None = None
    unit: str | None = None
    section: str | None = None          # Abschnittsname
    move_open: bool = False             # offene Einträge mitverschieben


@app.post("/api/items")
def api_item_upsert(body: ItemBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    sid = sections.id_for(body.section) if body.section else None
    existing = db.find_item(body.name)
    if existing:
        db.update_item(existing["id"], name=body.name, aliases=body.aliases,
                       default_qty=body.default_qty, unit=body.unit, section_id=sid)
    else:
        db.upsert_item(body.name, aliases=body.aliases, default_qty=body.default_qty,
                       unit=body.unit, section_id=sid)
    moved = 0
    if body.move_open and sid:
        sl = _list_for(_user(x_einkauf_user, user))
        for t in sl.open_tasks():
            if t["title"].lower() == body.name.lower() and t.get("section_id") != sid:
                sl.client.patch_task(t["id"], section_id=sid)
                cache.upsert_local(sl.client.task(t["id"]))
                moved += 1
    return {"ok": True, "moved": moved}


@app.get("/api/catalog")
def api_catalog():
    """Artikelstamm gruppiert nach Abschnitt, in Abschnittsreihenfolge."""
    groups: dict[str, list] = {name: [] for name in sections.names()}
    groups["Ohne Abschnitt"] = []
    names = sections.by_id()
    for it in db.items():
        groups.get(names.get(it["section_id"], "Ohne Abschnitt"), groups["Ohne Abschnitt"]).append(it)
    return [{"section": k, "items": v} for k, v in groups.items() if v]


class ImportBody(BaseModel):
    overwrite: bool = False


@app.post("/api/items/import")
def api_items_import(body: ImportBody):
    from .catalog import read_catalog
    return db.import_catalog(read_catalog(), overwrite=body.overwrite)


@app.delete("/api/items/{item_id}")
def api_item_delete(item_id: int):
    db.delete_item(item_id)
    return {"ok": True}


@app.get("/api/stores")
def api_stores():
    out = []
    for s in db.stores():
        names = sections.by_id()
        order = [names.get(x, x) for x in db.store_order(s["id"])]
        out.append(s | {"order": order or sections.names()})
    return out


class StoreBody(BaseModel):
    name: str
    label_id: str | None = None
    create_label: bool = False          # Label mit dem Ladennamen in OpenTodo anlegen
    order: list[str] = []


@app.post("/api/stores")
def api_store_upsert(body: StoreBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    label_id = body.label_id
    if body.create_label and not label_id:
        c = _client_for(_user(x_einkauf_user, user))
        existing = next((l for l in c.labels() if l["name"].lower() == body.name.lower()), None)
        label_id = existing["id"] if existing else c.create_label(body.name)["id"]
    sid = db.upsert_store(body.name, label_id)
    if body.order:
        m = sections.by_name()
        db.set_store_order(sid, [m[n] for n in body.order if n in m])
    return {"ok": True, "id": sid, "label_id": label_id}


class StoresOrder(BaseModel):
    names: list[str]


@app.post("/api/stores/order")
def api_stores_order(body: StoresOrder):
    db.set_stores_order(body.names)
    return {"ok": True}


@app.delete("/api/stores/{store_id}")
def api_store_delete(store_id: int):
    db.delete_store(store_id)
    return {"ok": True}


@app.get("/api/sections")
def api_sections():
    meta = db.section_meta()
    out = []
    for sec in sections.all():
        icon, color = sections.default_meta(sec["name"])
        m = meta.get(sec["id"], {})
        out.append({"id": sec["id"], "name": sec["name"], "position": sec["position"],
                    "icon": m.get("icon") or icon, "color": m.get("color") or color})
    return {"sections": out, "icons": sections.ICONS, "colors": sections.COLORS}


class SectionBody(BaseModel):
    name: str
    icon: str | None = None
    color: str | None = None


@app.post("/api/sections")
def api_section_create(body: SectionBody, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    c = _client_for(_user(x_einkauf_user, user))
    if sections.id_for(body.name):
        raise HTTPException(400, msg("section_exists"))
    rows = sections.all()
    pos = (max((r["position"] or 0) for r in rows) + 1) if rows else 0
    created = c.create_section(body.name, config.settings.project_id, position=pos)
    sections.refresh(c)
    if body.icon or body.color:
        db.set_section_meta(created["id"], body.icon, body.color)
    return {"ok": True, "id": created["id"]}


class SectionsOrder(BaseModel):
    ids: list[str]


@app.post("/api/sections/order")
def api_sections_order(body: SectionsOrder, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    """Reihenfolge der Abschnitte (gilt für „Alle" und in OpenTodo)."""
    c = _client_for(_user(x_einkauf_user, user))
    known = sections.by_id()
    for i, sid in enumerate(body.ids):
        if sid in known:
            c.patch_section(sid, position=i)
    sections.refresh(c)
    cache.version += 1
    return {"ok": True}


class SectionPatch(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None


@app.patch("/api/sections/{section_id}")
def api_section_patch(section_id: str, body: SectionPatch, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    if section_id not in sections.by_id():
        raise HTTPException(404, msg("section_missing"))
    if body.name:
        c = _client_for(_user(x_einkauf_user, user))
        c.patch_section(section_id, name=body.name)
        sections.refresh(c)
    if body.icon or body.color:
        db.set_section_meta(section_id, body.icon, body.color)
    return {"ok": True}


@app.delete("/api/sections/{section_id}")
def api_section_delete(section_id: str, x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    if section_id not in sections.by_id():
        raise HTTPException(404, msg("section_missing"))
    c = _client_for(_user(x_einkauf_user, user))
    c.delete_section(section_id)
    sections.refresh(c)
    full_sync()
    return {"ok": True}


@app.get("/api/labels")
def api_labels(x_einkauf_user: str | None = Header(None), user: str | None = Query(None)):
    return _client_for(_user(x_einkauf_user, user)).labels()


@app.get("/api/templates")
def api_templates():
    return [{"name": n, "items": db.template_detail(n)} for n in db.templates()]


class TemplateBody(BaseModel):
    name: str
    items: list[dict]   # {name, qty?, unit?}


@app.post("/api/templates")
def api_template_upsert(body: TemplateBody):
    positions = []
    for it in body.items:
        found = db.find_item(it["name"])
        iid = found["id"] if found else db.upsert_item(it["name"])
        positions.append((iid, it.get("qty"), it.get("unit")))
    db.upsert_template(body.name, positions)
    return {"ok": True}


@app.delete("/api/templates/{name}")
def api_template_delete(name: str):
    db.delete_template(name)
    return {"ok": True}


class UserBody(BaseModel):
    name: str
    token: str


@app.post("/api/users")
def api_user_set(body: UserBody):
    # Token prüfen, bevor er abgelegt wird
    try:
        me = OpenTodoClient(config.require_url(), body.token).me()
    except OpenTodoError as e:
        raise HTTPException(400, msg("token_rejected", status=e.status))
    c = OpenTodoClient(config.require_url(), body.token)
    if not config.settings.project_id:
        bootstrap.resolve(c)
        cache.project_id = config.settings.project_id
    visible = any(p["id"] == config.settings.project_id for p in c.projects())
    if not visible:
        raise HTTPException(400, msg("project_invisible", name=me["user"]["name"], project=config.settings.project_name))
    if me["auth"]["scope"] not in ("full", "admin"):
        raise HTTPException(400, msg("scope_low", scope=me["auth"]["scope"]))
    db.set_user_token(body.name, body.token)
    _clients.pop(body.name, None)
    return {"ok": True, "opentodo_user": me["user"]["name"], "scope": me["auth"]["scope"]}


@app.delete("/api/users/{name}")
def api_user_delete(name: str):
    db.delete_user(name)
    _clients.pop(name, None)
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
