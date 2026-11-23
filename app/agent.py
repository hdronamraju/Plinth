"""Claude tool-use agent. Trust rules from CLAUDE.md / PLAN.md §3 live in the system prompt and in
server-side guards (quote verification, forced abstain)."""
from __future__ import annotations

import bisect
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
FULL_TEXT_HITS = 4
FULL_TEXT_CHARS = 3500

SYSTEM = f"""You are Plinth, an assistant that helps Piedmont, CA homeowners check a project against the \
planning code and prepare questions for city planning staff. The knowledge base is the only source of \
facts. Code edition: {knowledge.CODE_EDITION}.

Rules (never break them):
1. Make no factual claim about code, policy or staff positions without searching first (search_knowledge / \
get_section) and quoting the source as a markdown blockquote (> exact text) under a bullet that names its \
cite. Quotes must be copied verbatim from tool results.
2. Label each part of an answer with one of: **Code says**, **City policy says**, **Staff have said \
(YYYY-MM-DD)**, **Needs staff**. The label goes at the start of each evidence bullet (rule 7).
3. If the search returns nothing relevant, abstain: say the knowledge base does not support an answer, \
label it **Needs staff**, and offer to add it to the staff questions (add_staff_question). Never guess.
4. Never say "approved", "allowed to" or "you can". Say "the code allows" and quote it.
5. Precedent is not law. Check its scope and status. Only cite `current` precedent; say its date and \
that it is a staff answer, not code. If code and precedent conflict, show both and mark **Needs staff**.
6. Property facts come from get_property; owner-entered facts are unconfirmed. Don't assume the zone \
if it is blank; ask the user.
7. Answer format. No preamble, no restating the question, no narrating your searches, no sign-off.
   - Line 1: the answer in one or two plain sentences, all in bold. Use "the code allows / requires / does \
not address", never "you can". If the knowledge base does not settle it, start with **Needs staff:** and say \
what is unresolved.
   - Then a blank line and the evidence as "- " bullets, one point each, each starting with its label: \
**Code says** (cite), **City policy says** (cite), **Staff have said (YYYY-MM-DD)** (cite), **Needs staff**.
   - Put each quote on its own line right under its bullet, starting at the beginning of the line with `> `. \
Never indent a quote and never put it inside the bullet text.
   - At most one short closing line, and only to offer adding a staff question ("Add this to your staff \
questions?").
   - Keep it short: usually 2 to 5 bullets. Ask a clarifying question only when an answer is impossible \
without it (for example, the zone is unknown); then ask it as the bold first line, with no bullets.
   - You do not give legal advice or decide permits.
Shape of an answer (placeholders, not real text):
**The code sets a minimum rear setback for this zone; whether a raised deck counts toward it needs staff.**

- **Code says** (City Code §17.X.XXX): states the rear setback.
> <exact text copied from the section>
- **Needs staff:** whether a deck of this height is a "structure" for setback purposes.

Add this to your staff questions?
8. Staff precedent may not be available to you. Use the **Staff have said (YYYY-MM-DD)** label only for a \
precedent record that a search actually returned. NEVER say or imply that no precedent exists, that staff \
have not addressed something, or that you searched precedent and found nothing: you cannot know that. When \
a question turns on a staff judgment, write **Needs staff** and say nothing about precedent.
9. Copy blockquotes from the full text in tool results. Search results include the full text of the top \
passages; use get_section for any code section or document page (for example design-guidelines:p022) \
whose text you need in full. Never quote from a cut-off snippet or paraphrase inside a blockquote.
10. Never say that something is not on, not allowed by, or not covered by a list, table or section unless you \
have read all of it. Lists and tables in the guidelines run across several pages, and search results may show \
only one of them (a hit with next_page or prev_page is one page of a longer document). If a passage looks like \
part of a longer list, read the rest first with get_section("source:pNNN-pNNN"). If you have not read it all, \
say "I only read part of the list" and do not claim anything is absent. The guidelines' list of exceptions to \
design review permits (section 2.05) is design-guidelines:p018-p022.
11. The KNOWLEDGE BASE list below is everything you can search. Choose the source that fits the question and pass \
its id as `source` when you know where the answer lives; search without a source when you do not. If a question \
depends on a topic no listed source covers, or on a document marked not loaded, say it is not in the knowledge \
base and mark it **Needs staff**. Do not guess from a nearby source.
12. Search with more than one wording: put the user's words in `query` and one to three other phrasings in `also` \
(plain words and the code's likely terms, such as "fence" and "wall", or "height" and "grade").

{knowledge.catalog_text()}
To export questions to PDF, call load_skill("export-staff-questions") first and follow it."""

TOOLS = [
    {"name": "search_knowledge", "description": "Search the Piedmont knowledge base (city code, design guidelines, "
     "policies, staff precedent). Returns ranked passages with cite, authority, date and status.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "also": {"type": "array", "items": {"type": "string"}, "maxItems": 3,
                  "description": "1-3 other wordings of the same question (plain words and the code's likely terms); "
                                 "results for all wordings are merged"},
         "source": {"type": "string", "description": "optional source id, e.g. ch17"},
         "authority": {"type": "string", "enum": ["binding", "official", "staff"]}}, "required": ["query"]}},
    {"name": "list_sources", "description": "List every document set in the knowledge base with what it covers, "
     "plus the city documents that are not loaded. Use it to choose a source or to confirm something is not available.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_section", "description": "Full text of one code section (e.g. 17.20.040) or one page of a "
     "document (e.g. design-guidelines:p022, policy-window-replacement:p001, page-design-review:p002), or a run "
     "of up to 6 pages (e.g. design-guidelines:p018-p022).",
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
                                property_address=address, also=args.get("also"))
        ctx["retrieved"].extend(h["snippet"] for h in hits)
        for n, h in enumerate(hits):  # full text of the top passages, so quotes are not cut off
            if h["authority"] == "staff":
                ctx["staff_seen"] = True
            try:
                _, body = knowledge.front_matter(ROOT / h["path"])
            except Exception:
                continue
            ctx["retrieved"].append(body)
            h.update(knowledge.neighbors(h.get("doc_id", "")))   # next_page / prev_page for page documents
            if n < FULL_TEXT_HITS:
                h["text"] = body[:FULL_TEXT_CHARS]
        if not hits:
            return "NO MATCHES. The knowledge base does not support an answer. Abstain and mark Needs staff."
        return json.dumps(hits, ensure_ascii=False)
    if name == "list_sources":
        return json.dumps(knowledge.catalog(), ensure_ascii=False)
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


QUOTE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?>[ \t]?(.+)$", re.M)  # also quotes nested under a bullet
GAP = 12  # words of interleaved text (e.g. a neighbouring table column) allowed between quoted words


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘…*_]", "", s)).strip().lower()


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9%$§]+", _norm(s))


class _Pool:
    """Words of everything retrieved this turn, indexed for ordered matching."""
    def __init__(self, retrieved: list[str]):
        self.text = _norm(" ".join(retrieved))
        self.words = _words(self.text)
        self.pos: dict[str, list[int]] = {}
        for i, w in enumerate(self.words):
            self.pos.setdefault(w, []).append(i)

    def has(self, quote: str) -> bool:
        """True if the quote is a verbatim passage, or the same words in the same order with only a few
        words of other text between them. The PDF text stores table columns interleaved, so a faithful
        quote of one cell is not a plain substring. Invented wording still fails: every word of the
        quote must appear, in order, nearly adjacent."""
        if quote in self.text:
            return True
        q = _words(quote)
        if len(q) < 4 or q[0] not in self.pos:
            return False
        budget = max(6, len(q) // 5)
        seen: set[tuple[int, int, int]] = set()

        def walk(i: int, at: int, used: int) -> bool:
            if i == len(q):
                return True
            if (i, at, used) in seen:
                return False
            seen.add((i, at, used))
            lst = self.pos.get(q[i], [])
            k = bisect.bisect_right(lst, at)
            for nxt in lst[k:k + 3]:
                gap = nxt - at - 1
                if gap > GAP or used + gap > budget:
                    break
                if walk(i + 1, nxt, used + gap):
                    return True
            return False
        return any(walk(1, start, 0) for start in self.pos[q[0]][:200])


def verify_quotes(answer: str, retrieved: list[str]) -> tuple[str, int]:
    """Replace blockquotes that don't appear in anything retrieved this turn."""
    pool = _Pool(retrieved)
    bad = 0

    def fix(m):
        nonlocal bad
        q = _norm(m.group(1))
        if not q or all(pool.has(p) for p in re.split(r"\s*\.\.\.\s*", q) if p):
            return m.group(0)
        bad += 1
        return "> [quote removed: could not be matched to a retrieved source]"
    return QUOTE.sub(fix, answer), bad


_NO_PREC = re.compile(r"\b(nothing|no match(?:es)?|no staff|none|found no|not find|no record|no precedent|"
                      r"did not (?:find|return)|returned no|not have)\b", re.I)
_LABEL_LINE = re.compile(r"^\W*(?:staff have said)\b[^\n]*$", re.I)


def _is_absence_claim(sent: str) -> bool:
    """A sentence saying staff precedent was searched and not found, or that staff haven't addressed it."""
    if re.search(r"\bstaff (?:haven't|have not|hasn't|has not) (?:addressed|said|ruled|answered)", sent, re.I):
        return True
    return bool(re.search(r"precedent", sent, re.I) and _NO_PREC.search(sent)
                and re.match(r"\W*(?:I|A|My|The)\b.*\b(?:search|searched|found|knowledge base|has no)", sent, re.I))


def strip_precedent_claims(text: str, staff_seen: bool) -> tuple[str, int]:
    """Staff precedent can be missing from this deployment, so the agent cannot know that none exists.
    Drop any sentence or "Staff have said" paragraph that claims so, unless a staff record was returned."""
    if staff_seen:
        return text, 0
    dropped = 0
    paras = re.split(r"\n{2,}", text)
    out: list[str] = []
    for p in paras:
        body = re.sub(r"^\W*staff have said[^:\n]*:?\W*", "", p, flags=re.I).strip() if _LABEL_LINE.match(p) else None
        if len(p) <= 260 and re.search(r"staff have said", p, re.I) and _NO_PREC.search(p):
            dropped += 1                       # e.g. "City policy says / Staff have said: ... found nothing"
            continue
        if body and _NO_PREC.search(body):
            dropped += 1                       # a "Staff have said: nothing / no precedent" paragraph
            continue
        if out and re.fullmatch(r"\W*staff have said\W*(?:\(.*?\))?\W*", out[-1], re.I) and _NO_PREC.search(p):
            out.pop(); dropped += 1            # bare label on its own line followed by the claim
            continue
        lines = []
        for line in p.split("\n"):             # per line, so a claim inside a bullet list is found
            sents = re.split(r"(?<=[.!?])\s+(?=[A-Z*])", line)
            kept = [x for x in sents if not _is_absence_claim(x)]
            dropped += len(sents) - len(kept)
            if kept and re.search(r"\w", " ".join(kept)):
                lines.append(" ".join(kept))
        if lines:
            out.append("\n".join(lines))
    while out and re.fullmatch(r"\W*staff have said\W*(?:\(.*?\))?\W*", out[-1], re.I):
        out.pop(); dropped += 1                # a bare label left with nothing under it
    return "\n\n".join(out), dropped


EMPTY_FALLBACK = ("**Needs staff.** I could not put together an answer to that from the knowledge base. "
                  "Please try rephrasing, or add it to the staff questions.")


# Prompt caching. Each round of the tool loop resends the same tools + system prompt + conversation so far,
# and input was ~80% of spend with nothing cached. Two breakpoints (5-minute TTL, refreshed by every read):
#  - an explicit one on the system prompt, so tools + system are shared by every session and survive
#    whatever happens in `messages`;
#  - top-level automatic caching, which moves forward with the conversation, so round N+1 reads rounds 1..N.
# Caching is a prefix match: SYSTEM and TOOLS must stay byte-identical between calls (no dates, ids or
# per-user text in them; put anything dynamic in `messages`).
CACHE = {"type": "ephemeral"}
SYSTEM_BLOCKS = [{"type": "text", "text": SYSTEM, "cache_control": CACHE}]
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def _call(client, msgs: list, usage: dict, **extra):
    """One Messages API call with caching on; adds the response's token counts to `usage`."""
    resp = client.messages.create(model=MODEL, max_tokens=2000, system=SYSTEM_BLOCKS, tools=TOOLS,
                                  messages=msgs, cache_control=CACHE, **extra)
    u = getattr(resp, "usage", None)
    for k in USAGE_KEYS:
        usage[k] += (getattr(u, k, 0) or 0) if u is not None else 0
    usage["calls"] += 1
    return resp


def _final_answer(client, msgs: list, usage: dict) -> str:
    """The tool loop ended with no text (e.g. it ran out of turns). Ask once more for a plain answer."""
    try:
        if msgs and msgs[-1]["role"] == "assistant":
            msgs.pop()                                   # drop the empty assistant turn
        resp = _call(client, msgs, usage, tool_choice={"type": "none"})
        text = "".join(getattr(b, "text", "") or (b.get("text", "") if isinstance(b, dict) else "")
                       for b in resp.content)
        if text.strip():
            msgs.append({"role": "assistant", "content": [{"type": "text", "text": text}]})
            return text
    except Exception:
        pass
    msgs.append({"role": "assistant", "content": [{"type": "text", "text": EMPTY_FALLBACK}]})
    return EMPTY_FALLBACK


def chat(sid: str, user_text: str, client=None) -> dict:
    state = store.load(sid)
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Export it and restart the server.")
        import anthropic
        client = anthropic.Anthropic()
    msgs = state["messages"] + [{"role": "user", "content": user_text}]
    ctx = {"retrieved": [], "changed": False, "searched": False, "staff_seen": False}
    text = ""
    usage = dict.fromkeys(USAGE_KEYS, 0) | {"calls": 0}
    for _ in range(MAX_TURNS):
        resp = _call(client, msgs, usage)
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
    if not text.strip():
        text = _final_answer(client, msgs, usage)
    text, removed = verify_quotes(text, ctx["retrieved"])
    text, _ = strip_precedent_claims(text, ctx["staff_seen"])
    notes = []
    if removed:
        notes.append(f"{removed} quote(s) removed because they could not be matched to the knowledge base.")
    if not ctx["searched"] and re.search(r"17\.\d\d\.\d+|§|\bcode\b", text, re.I):
        notes.append("This answer did not consult the knowledge base. Treat it as **Needs staff**.")
    state["messages"] = msgs
    store.save(sid, state)
    # One log line per answer (Fly keeps stdout): token use and cache hits, so cost per question is measurable.
    print(json.dumps({"event": "chat_usage", "model": MODEL, **usage}), flush=True)
    return {"answer": text, "notes": notes, "staff_questions": state["staff_questions"],
            "pdfs": state["pdfs"], "usage": {"model": MODEL, **usage}}


EXTRACT_TOOL = {"name": "record_facts", "description": "Record property facts found in the pasted text. "
    "Include only fields the text explicitly states. Copy values as written. Omit anything not stated.",
    "input_schema": {"type": "object", "properties": {k: {"type": "string"} for k in prop.FIELDS}}}


def _grounded(field: str, value: str, text: str) -> bool:
    """True only if `value` is literally in `text`. Short values must match a whole token, and a zone
    must be written as "zone X", so a stray letter or digit can't pass as a fact."""
    if field == "zone":
        return bool(re.search(r"zone\W{0,3}(?:is\s+)?" + re.escape(value.strip()) + r"(?![A-Za-z0-9])", text, re.I))
    v = re.sub(r"[\s,\$]", "", value.lower())
    if not v:
        return False
    if len(v) <= 3:
        return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(value.strip()) + r"(?![A-Za-z0-9])", text, re.I))
    return v in re.sub(r"[\s,\$]", "", text.lower())


def extract_property_facts(text: str, client=None) -> tuple[dict, list[str]]:
    """Pull property facts out of pasted text. Values not literally present in the text are dropped,
    so the model cannot invent facts. Returns (facts, dropped_field_names)."""
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Export it and restart the server.")
        import anthropic
        client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL, max_tokens=800, tools=[EXTRACT_TOOL], tool_choice={"type": "tool", "name": "record_facts"},
        system="Extract property facts from text the user pasted. Never infer, convert or guess. If unsure, omit.",
        messages=[{"role": "user", "content": "<pasted>\n" + text[:20000] + "\n</pasted>"}])
    raw = {}
    for b in resp.content:
        b = b.model_dump() if hasattr(b, "model_dump") else b
        if b["type"] == "tool_use":
            raw = b["input"]
    keep, dropped = {}, []
    for k, v in raw.items():
        if k in prop.FIELDS and isinstance(v, str) and v.strip():
            if _grounded(k, v, text):
                keep[k] = v.strip()
            else:
                dropped.append(k)
    return keep, dropped
