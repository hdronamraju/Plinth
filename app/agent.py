"""Claude tool-use agent. Trust rules from CLAUDE.md / PLAN.md §3 live in the system prompt and in
server-side guards (quote verification, forced abstain)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import uuid
from pathlib import Path

from . import knowledge, store
from . import property as prop

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "export-staff-questions"
MODEL = os.environ.get("PLINTH_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 8

SYSTEM = f"""You are Plinth, an assistant that helps Piedmont, CA homeowners check a project against the \
planning code and prepare questions for city planning staff. The knowledge base is the only source of \
facts. Code edition: {knowledge.CODE_EDITION}.

Rules (never break them):
1. Make no factual claim about code, policy or staff positions without searching first (search_knowledge / \
get_section) and quoting the source inline as a markdown blockquote (> exact text) followed by its cite. \
Quotes must be copied verbatim from tool results.
2. Label each part of an answer with one of: **Code says**, **City policy says**, **Staff have said \
(YYYY-MM-DD)**, **Needs staff**. 
3. If the search returns nothing relevant, abstain: say the knowledge base does not support an answer, \
label it **Needs staff**, and offer to add it to the staff questions (add_staff_question). Never guess.
4. Never say "approved", "allowed to" or "you can". Say "the code allows" and quote it.
5. Precedent is not law. Check its scope and status. Only cite `current` precedent; say its date and \
that it is a staff answer, not code. If code and precedent conflict, show both and mark **Needs staff**.
6. Property facts come from get_property; owner-entered facts are unconfirmed. Don't assume the zone \
if it is blank; ask the user.
7. Be concise and plain-spoken. You do not give legal advice or decide permits.
To export questions to PDF, call load_skill("export-staff-questions") first and follow it."""

TOOLS = [
    {"name": "search_knowledge", "description": "Search the Piedmont knowledge base (city code, design guidelines, "
     "policies, staff precedent). Returns ranked passages with cite, authority, date and status.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "source": {"type": "string", "description": "optional source id, e.g. ch17"},
         "authority": {"type": "string", "enum": ["binding", "official", "staff"]}}, "required": ["query"]}},
    {"name": "get_section", "description": "Full text of one code section, e.g. 17.20.040.",
     "input_schema": {"type": "object", "properties": {"number": {"type": "string"}}, "required": ["number"]}},
    {"name": "get_property", "description": "The homeowner's property record with each fact's source.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "add_staff_question", "description": "Add an open question for planning staff.",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "question": {"type": "string"}, "context": {"type": "string"},
         "code_refs": {"type": "array", "items": {"type": "string"},
                       "description": "section numbers retrieved, e.g. 17.20.040"},
         "proposed_reading": {"type": "string"}}, "required": ["title", "question", "proposed_reading"]}},
    {"name": "list_staff_questions", "description": "List open staff questions.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "update_staff_question", "description": "Edit or delete a staff question by id.",
     "input_schema": {"type": "object", "properties": {
         "id": {"type": "string"}, "title": {"type": "string"}, "question": {"type": "string"},
         "context": {"type": "string"}, "code_refs": {"type": "array", "items": {"type": "string"}},
         "proposed_reading": {"type": "string"}, "delete": {"type": "boolean"}}, "required": ["id"]}},
    {"name": "load_skill", "description": "Load a skill's instructions.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string", "enum": ["export-staff-questions"]}},
                      "required": ["name"]}},
    {"name": "export_staff_pdf", "description": "Generate the fillable PDF from open staff questions. "
     "Load the export-staff-questions skill first.",
     "input_schema": {"type": "object", "properties": {
         "project_description": {"type": "string"},
         "question_ids": {"type": "array", "items": {"type": "string"}, "description": "ordered subset; default all"}}}},
]


def _export_module():
    spec = importlib.util.spec_from_file_location("plinth_export", SKILL_DIR / "export.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_pdf(state: dict, project_description: str = "", question_ids: list | None = None) -> dict:
    """Build the PDF from state; quotes are re-fetched from the lake, not trusted from the model."""
    qs = state["staff_questions"]
    if question_ids:
        by = {q["id"]: q for q in qs}
        qs = [by[i] for i in question_ids if i in by]
    if not qs:
        return {"error": "No open staff questions to export."}
    record = state.get("property")
    address = record["facts"]["address"]["value"] if record else "Address not provided"
    facts = [(prop.LABELS.get(k, k.title()), v["value"], v["source"])
             for k, v in (record["facts"].items() if record else []) if k not in ("latitude", "longitude")]
    items = []
    for q in qs:
        quote, cite = "", ""
        for ref in q.get("code_refs", []):
            secs = knowledge.get_section(ref)
            if secs:
                body = re.sub(r"^# .*\n", "", secs[0]["text"]).strip()
                quote, cite = body, secs[0]["cite"]
                break
        precedent = ""
        hits = [h for h in knowledge.search(q["question"], authority="staff", k=1,
                                            property_address=address) if h["status"] == "current"]
        if hits:
            h = hits[0]
            note = " (pending confirmation)" if h.get("pending") else ""
            precedent = f"{h['cite']}{note}, scope {h.get('scope')}: {h['snippet']}"
        items.append({"id": q["id"], "title": q["title"], "context": q.get("context") or q["question"],
                      "code_ref": quote, "code_cite": cite, "precedent": precedent,
                      "proposed": q.get("proposed_reading", "")})
    n = len(state["pdfs"]) + 1
    doc_id = state.setdefault("doc_id", "PL-" + uuid.uuid4().hex[:6].upper())
    out = store.DIR / f"{doc_id}-v{n}.pdf"
    store.DIR.mkdir(exist_ok=True)
    _export_module().build_pdf(out, doc_id, n, address, facts, project_description, items)
    state["pdfs"].append({"file": out.name, "version": n, "doc_id": doc_id, "count": len(items)})
    return {"ok": True, "file": out.name, "doc_id": doc_id, "version": n, "questions": len(items)}


def run_tool(name: str, args: dict, state: dict, ctx: dict) -> str:
    address = state["property"]["facts"]["address"]["value"] if state.get("property") else None
    if name == "search_knowledge":
        hits = knowledge.search(args["query"], args.get("source"), args.get("authority"),
                                property_address=address)
        ctx["retrieved"].extend(h["snippet"] for h in hits)
        for h in hits:  # also allow quoting from the full section text
            if h["kind"] == "code":
                ctx["retrieved"].extend(s["text"] for s in knowledge.get_section(h["doc_id"].split(":")[-1]))
        if not hits:
            return "NO MATCHES. The knowledge base does not support an answer. Abstain and mark Needs staff."
        return json.dumps(hits, ensure_ascii=False)
    if name == "get_section":
        secs = knowledge.get_section(args["number"])
        ctx["retrieved"].extend(s["text"] for s in secs)
        return json.dumps(secs, ensure_ascii=False) if secs else "NO SUCH SECTION in the knowledge base."
    if name == "get_property":
        return prop.summary(state["property"]) if state.get("property") else "No property entered yet."
    if name == "add_staff_question":
        q = {"id": "sq" + uuid.uuid4().hex[:6], **{k: args.get(k, "") for k in
             ("title", "question", "context", "proposed_reading")}, "code_refs": args.get("code_refs", [])}
        state["staff_questions"].append(q)
        ctx["changed"] = True
        return f"Added {q['id']}."
    if name == "list_staff_questions":
        return json.dumps(state["staff_questions"], ensure_ascii=False) or "[]"
    if name == "update_staff_question":
        qs = state["staff_questions"]
        for q in list(qs):
            if q["id"] == args["id"]:
                if args.get("delete"):
                    qs.remove(q)
                else:
                    q.update({k: v for k, v in args.items() if k not in ("id", "delete")})
                ctx["changed"] = True
                return "Updated."
        return "No such question id."
    if name == "load_skill":
        return (SKILL_DIR / "SKILL.md").read_text()
    if name == "export_staff_pdf":
        r = make_pdf(state, args.get("project_description", ""), args.get("question_ids"))
        ctx["changed"] = True
        return json.dumps(r)
    return f"Unknown tool {name}"


QUOTE = re.compile(r"^>\s?(.+)$", re.M)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘…*_]", "", s)).strip().lower()


def verify_quotes(answer: str, retrieved: list[str]) -> tuple[str, int]:
    """Replace blockquotes that don't appear in anything retrieved this turn."""
    pool = _norm(" ".join(retrieved))
    bad = 0

    def fix(m):
        nonlocal bad
        q = _norm(m.group(1))
        if not q or q in pool or all(p in pool for p in re.split(r"\s*\.\.\.\s*", q) if p):
            return m.group(0)
        bad += 1
        return "> [quote removed: could not be matched to a retrieved source]"
    return QUOTE.sub(fix, answer), bad


def chat(sid: str, user_text: str, client=None) -> dict:
    state = store.load(sid)
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Export it and restart the server.")
        import anthropic
        client = anthropic.Anthropic()
    msgs = state["messages"] + [{"role": "user", "content": user_text}]
    ctx = {"retrieved": [], "changed": False, "searched": False}
    text = ""
    for _ in range(MAX_TURNS):
        resp = client.messages.create(model=MODEL, max_tokens=2000, system=SYSTEM, tools=TOOLS, messages=msgs)
        raw = [b.model_dump() if hasattr(b, "model_dump") else b for b in resp.content]
        blocks = [{k: b[k] for k in (("type", "text") if b["type"] == "text" else ("type", "id", "name", "input"))}
                  for b in raw if b["type"] in ("text", "tool_use")]
        msgs.append({"role": "assistant", "content": blocks})
        uses = [b for b in blocks if b["type"] == "tool_use"]
        text = "".join(b["text"] for b in blocks if b["type"] == "text")
        if not uses:
            break
        results = []
        for u in uses:
            if u["name"] in ("search_knowledge", "get_section"):
                ctx["searched"] = True
            results.append({"type": "tool_result", "tool_use_id": u["id"],
                            "content": run_tool(u["name"], u["input"], state, ctx)})
        msgs.append({"role": "user", "content": results})
    text, removed = verify_quotes(text, ctx["retrieved"])
    notes = []
    if removed:
        notes.append(f"{removed} quote(s) removed because they could not be matched to the knowledge base.")
    if not ctx["searched"] and re.search(r"17\.\d\d\.\d+|§|\bcode\b", text, re.I):
        notes.append("This answer did not consult the knowledge base. Treat it as **Needs staff**.")
    state["messages"] = msgs
    store.save(sid, state)
    return {"answer": text, "notes": notes, "staff_questions": state["staff_questions"],
            "pdfs": state["pdfs"]}
