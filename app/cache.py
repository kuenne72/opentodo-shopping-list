"""Cache der offenen Liste plus Verteiler für Server-Sent Events (Plan 4.3, 4.5).

Der Cache hält die Aufgaben des Projekts „Einkauf" wie die REST-API sie liefert.
Webhook-Ereignisse aktualisieren einzelne Einträge; ein Vollabgleich läuft
beim Start und periodisch als Fallback.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import OrderedDict
from typing import Any


class ListCache:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()  # delivery ids
        self.version = 0
        self.last_full_sync: float = 0.0
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------ Daten
    def replace_all(self, tasks: list[dict]) -> None:
        with self._lock:
            self._tasks = {
                t["id"]: t
                for t in tasks
                if t.get("project_id") == self.project_id and not t.get("deleted_at")
            }
            self.version += 1
            self.last_full_sync = time.time()
        self._notify({"type": "reset", "version": self.version})

    def apply_event(self, delivery_id: str, event: str, task: dict | None) -> bool:
        """Wendet ein Webhook-Ereignis an. Liefert False bei Duplikat oder fremdem Projekt."""
        if delivery_id in self._seen:
            return False
        self._remember(delivery_id)
        if not task or not event.startswith("task."):
            return False
        tid = task["id"]
        with self._lock:
            belongs = task.get("project_id") == self.project_id and not task.get("deleted_at")
            if event == "task.deleted" or not belongs:
                existed = self._tasks.pop(tid, None) is not None
                if not existed:
                    return False
                kind = "removed"
            else:
                kind = "updated" if tid in self._tasks else "added"
                self._tasks[tid] = task
            self.version += 1
        self._notify({"type": kind, "version": self.version, "task_id": tid, "event": event})
        return True

    def upsert_local(self, task: dict) -> None:
        """Nach eigenem Schreibvorgang den Stand sofort übernehmen."""
        with self._lock:
            if task.get("project_id") == self.project_id and not task.get("deleted_at"):
                self._tasks[task["id"]] = task
            else:
                self._tasks.pop(task["id"], None)
            self.version += 1
        self._notify({"type": "updated", "version": self.version, "task_id": task["id"], "event": "local"})

    def tasks(self, *, open_only: bool = True) -> list[dict]:
        with self._lock:
            rows = list(self._tasks.values())
        if open_only:
            rows = [t for t in rows if not t.get("completed_at")]
        return rows

    def _remember(self, delivery_id: str) -> None:
        self._seen[delivery_id] = time.time()
        while len(self._seen) > 2000:
            self._seen.popitem(last=False)

    # ------------------------------------------------------------ SSE
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def _notify(self, payload: dict[str, Any]) -> None:
        if not self._loop:
            return
        msg = json.dumps(payload)

        def _push():
            for q in list(self._subscribers):
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass

        try:
            self._loop.call_soon_threadsafe(_push)
        except RuntimeError:
            pass
