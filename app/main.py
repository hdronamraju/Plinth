"""Plinth prototype server.  uvicorn app.main:app --reload"""
from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import agent, store
from . import property as prop

STATIC = Path(__file__).parent / "static"


def sid_of(request: Request) -> str:
    sid = request.headers.get("x-session") or request.query_params.get("s", "")
    try:
        store.load(sid)
    except ValueError:
        raise ValueError("Missing or invalid X-Session header")
    return sid


async def index(request):
    return FileResponse(STATIC / "index.html")


async def session_new(request):
    return JSONResponse({"session": store.new_id()})


async def state_get(request):
    st = store.load(sid_of(request))
    rec = st["property"]
    return JSONResponse({"property": rec, "zone": prop.zone_info(rec) if rec else None,
                         "staff_questions": st["staff_questions"], "pdfs": st["pdfs"],
                         "messages": _history(st["messages"])})


def _history(msgs):
    out = []
    for m in msgs:
        if m["role"] == "user" and isinstance(m["content"], str):
            out.append({"role": "user", "text": m["content"]})
        elif m["role"] == "assistant":
            t = "".join(b.get("text", "") for b in m["content"] if b["type"] == "text")
            if t.strip():
                out.append({"role": "assistant", "text": t})
    return out


async def property_post(request):
    sid = sid_of(request)
    body = await request.json()
    st = store.load(sid)
    if body.get("address"):
        st["property"] = prop.build(body["address"])
    if st["property"] and body.get("facts"):
        prop.update_facts(st["property"], body["facts"])
    if st["property"] and body.get("confirmed") is not None:
        st["property"]["confirmed"] = bool(body["confirmed"])
    store.save(sid, st)
    rec = st["property"]
    return JSONResponse({"property": rec, "zone": prop.zone_info(rec) if rec else None})


async def chat_post(request):
    sid = sid_of(request)
    body = await request.json()
    text = (body.get("message") or "").strip()
    if not text:
        return JSONResponse({"error": "Empty message"}, status_code=400)
    try:
        return JSONResponse(agent.chat(sid, text))
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:  # surface API errors to the UI
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=502)


async def questions_put(request):
    sid = sid_of(request)
    st = store.load(sid)
    st["staff_questions"] = (await request.json())["staff_questions"]
    store.save(sid, st)
    return JSONResponse({"staff_questions": st["staff_questions"]})


async def export_post(request):
    sid = sid_of(request)
    body = await request.json()
    st = store.load(sid)
    r = agent.make_pdf(st, body.get("project_description", ""), body.get("question_ids"))
    store.save(sid, st)
    return JSONResponse(r, status_code=400 if "error" in r else 200)


async def pdf_get(request):
    sid = sid_of(request)
    st = store.load(sid)
    name = request.path_params["name"]
    if name not in {p["file"] for p in st["pdfs"]}:
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(store.DIR / name, media_type="application/pdf", filename=name)


async def on_error(request, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


app = Starlette(
    routes=[Route("/", index), Route("/api/session", session_new, methods=["POST"]),
            Route("/api/state", state_get), Route("/api/property", property_post, methods=["POST"]),
            Route("/api/chat", chat_post, methods=["POST"]),
            Route("/api/staff-questions", questions_put, methods=["PUT"]),
            Route("/api/export", export_post, methods=["POST"]),
            Route("/api/pdf/{name}", pdf_get),
            Mount("/static", StaticFiles(directory=STATIC))],
    exception_handlers={ValueError: on_error})
