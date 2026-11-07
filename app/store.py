"""Per-session JSON state in generated/ (gitignored). Prototype: no auth, one file per session id."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "generated"
EMPTY = {"property": None, "staff_questions": [], "messages": [], "pdfs": []}


def _path(sid: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", sid):
        raise ValueError("bad session id")
    return DIR / f"session-{sid}.json"


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def load(sid: str) -> dict:
    p = _path(sid)
    if p.exists():
        return {**json.loads(p.read_text())}
    return json.loads(json.dumps(EMPTY))


def save(sid: str, state: dict) -> None:
    DIR.mkdir(exist_ok=True)
    _path(sid).write_text(json.dumps(state, indent=2, ensure_ascii=False))
