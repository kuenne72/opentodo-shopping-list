"""Dünner Client für die OpenTodo-REST-API (Phase 1, Plan 3.2).

Deckt genau das ab, was der Einkaufsdienst braucht: Aufgaben lesen,
anlegen, ändern, abschließen; Abschnitte, Felder, Labels lesen.
Alle Aufrufe laufen über httpx mit Timeout und Retry auf 429/5xx.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx


class OpenTodoError(Exception):
    def __init__(self, status: int, body: Any, path: str):
        self.status = status
        self.body = body
        self.path = path
        super().__init__(f"HTTP {status} bei {path}: {body}")


class OpenTodoClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 15.0,
        retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    # ------------------------------------------------------------ intern
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        idempotent: bool = False,
    ) -> Any:
        headers = {}
        if idempotent:
            headers["Idempotency-Key"] = uuid.uuid4().hex
        delay = 0.5
        for attempt in range(self.retries + 1):
            resp = self._http.request(
                method, path, json=json, params=params, headers=headers
            )
            if resp.status_code in (429, 502, 503, 504) and attempt < self.retries:
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except ValueError:
                    body = resp.text
                raise OpenTodoError(resp.status_code, body, path)
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise RuntimeError("unreachable")

    # ------------------------------------------------------------ lesen
    def me(self) -> dict:
        return self._request("GET", "/api/v1/me")

    def projects(self) -> list[dict]:
        return self._request("GET", "/api/v1/projects")["projects"]

    def sections(self, project_id: str | None = None) -> list[dict]:
        rows = self._request("GET", "/api/v1/sections")["sections"]
        if project_id:
            rows = [s for s in rows if s["project_id"] == project_id]
        return [s for s in rows if not s.get("deleted_at")]

    def fields(self, project_id: str | None = None) -> list[dict]:
        rows = self._request("GET", "/api/v1/fields")["fields"]
        if project_id:
            rows = [f for f in rows if f["project_id"] == project_id]
        return [f for f in rows if not f.get("deleted_at")]

    def labels(self) -> list[dict]:
        rows = self._request("GET", "/api/v1/labels")["labels"]
        return [l for l in rows if not l.get("deleted_at")]

    def tasks(
        self,
        project_id: str | None = None,
        *,
        open_only: bool = False,
        completed_after_ms: int | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {}
        if completed_after_ms is not None:
            params["completed_after"] = completed_after_ms
        rows = self._request("GET", "/api/v1/tasks", params=params or None)["tasks"]
        rows = [t for t in rows if not t.get("deleted_at")]
        if project_id:
            rows = [t for t in rows if t.get("project_id") == project_id]
        if open_only:
            rows = [t for t in rows if not t.get("completed_at")]
        return rows

    def task(self, task_id: str) -> dict:
        return self._request("GET", f"/api/v1/tasks/{task_id}")

    # ------------------------------------------------------------ schreiben
    def create_task(
        self,
        title: str,
        *,
        project_id: str,
        section_id: str | None = None,
        labels: list[str] | None = None,
        fields: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"title": title, "project_id": project_id}
        if section_id:
            body["section_id"] = section_id
        if labels:
            body["labels"] = labels
        if fields:
            body["fields"] = fields
        if description:
            body["description"] = description
        return self._request("POST", "/api/v1/tasks", json=body, idempotent=True)

    def patch_task(self, task_id: str, **changes: Any) -> dict:
        """Teil-Update. `fields` wird serverseitig je Schlüssel gemergt,
        `labels` als Ganzes ersetzt."""
        return self._request("PATCH", f"/api/v1/tasks/{task_id}", json=changes)

    def complete_task(self, task_id: str, when_ms: int | None = None) -> dict:
        return self.patch_task(task_id, completed_at=when_ms or int(time.time() * 1000))

    def reopen_task(self, task_id: str) -> dict:
        return self.patch_task(task_id, completed_at=None)

    def create_section(self, name: str, project_id: str, position: int | None = None) -> dict:
        body: dict[str, Any] = {"name": name, "project_id": project_id}
        if position is not None:
            body["position"] = position
        return self._request("POST", "/api/v1/sections", json=body, idempotent=True)

    def patch_section(self, section_id: str, **changes: Any) -> dict:
        return self._request("PATCH", f"/api/v1/sections/{section_id}", json=changes)

    def delete_section(self, section_id: str) -> None:
        self._request("DELETE", f"/api/v1/sections/{section_id}")

    def create_label(self, name: str, color: str = "#64748b") -> dict:
        return self._request(
            "POST", "/api/v1/labels", json={"name": name, "color": color}, idempotent=True
        )

    def close(self) -> None:
        self._http.close()
