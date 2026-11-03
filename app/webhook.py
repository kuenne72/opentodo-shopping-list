"""Signaturprüfung für OpenTodo-Webhooks (Plan 4.1).

Signiert wird `<timestamp>.<raw body>` mit HMAC-SHA256, Schlüssel ist das
vollständige Secret inkl. Präfix `whsec_`. Header:
  X-OpenTodo-Timestamp  Unix-Sekunden des Versuchs
  X-OpenTodo-Signature  "v1=<hex>"
  X-OpenTodo-Delivery   Zustell-ID (für Dedupe)
"""

from __future__ import annotations

import hashlib
import hmac
import time


def sign(secret: str, timestamp: int | str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256)
    return "v1=" + mac.hexdigest()


def verify(
    secret: str,
    timestamp: str | None,
    body: bytes,
    signature: str | None,
    *,
    max_age: int = 300,
    now: float | None = None,
) -> bool:
    if not secret or not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if max_age and abs((now or time.time()) - ts) > max_age:
        return False
    return hmac.compare_digest(sign(secret, ts, body), signature)
