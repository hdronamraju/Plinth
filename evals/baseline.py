"""Baseline: ask a model the eval questions without Plinth's knowledge base or server checks.

Plinth's answers come from the model plus the knowledge base plus server checks. This asks the same
model (or another one) the same questions without them, so the score gap shows what Plinth adds.

Conditions:
  bare   the question only, the way a homeowner would type it into a chatbot; no tools
  rules  Plinth's answer rules (quote and cite, label each part, say Needs staff when unsure); no tools
  web    the same rules plus Claude's built-in web search and page fetch: "could a chatbot that can
         search replace Plinth?" Each row also records the searches, pages opened and cited URLs.

Usage:
  python evals/baseline.py --dry-run                      # show the prompt and question count; no API calls
  python evals/baseline.py --condition rules --limit 3    # try three questions first
  python evals/baseline.py --condition rules              # all 53
  python evals/baseline.py --condition bare
  python evals/baseline.py --condition web --limit 3      # costs more: searches plus the pages they return

Answers go to evals/runs/baseline-<condition>-<model>.jsonl, one line per question, in the same shape as the
Plinth runs. Re-running the same command skips questions already answered and retries any that failed.
Needs ANTHROPIC_API_KEY. Graded by hand or by an LLM against evals/README.md, like the Plinth runs.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUESTION_FILES = ("evals/lorita.yaml", "evals/general.yaml")   # retrieval-only entries (group G) have no question
# $/MTok: input, output, 5-minute cache write, cache read
PRICE = {"claude-sonnet-5-5": (2.0, 10.0, 2.5, 0.10), "claude-opus-5-5": (4.0, 20.0, 5.0, 0.20)}
SEARCH_PRICE = 10 / 1000          # $ per web search; page fetches are not charged beyond their tokens
MAX_SEARCHES = 5                  # web searches per question
MAX_FETCHES = 3                   # pages opened per question
PAGE_TOKENS = 20_000              # each opened page is cut to this many tokens (a full code chapter is far longer)
MAX_RESUMES = 4                   # a long search turn can pause; it is sent back this many times at most
WEB_TOOLS = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES},
             {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_FETCHES,
              "max_content_tokens": PAGE_TOKENS}]
# Saved on each row. Rows made with different settings are dropped and asked again, so one file is one setup.
CONFIG = {"web": {"max_searches": MAX_SEARCHES, "max_fetches": MAX_FETCHES, "page_tokens": PAGE_TOKENS}}
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

RULES = """You help Piedmont, California homeowners check a project against the city's planning code \
(Piedmont City Code Chapter 17, effective 2026-05-20) and the city's design guidelines and policies. \
{SOURCES}

Rules:
1. Make no factual claim about the code or city policy unless you are confident of it. When you quote the code, \
quote it as a markdown blockquote (> exact text) followed by its section number, for example (§17.20.040). \
{QUOTE}
2. Label each part of the answer with one of: **Code says**, **City policy says**, **Needs staff**.
3. If you are not sure, say so, label it **Needs staff**, and suggest asking city planning staff. Never guess.
4. Never say "approved", "allowed to" or "you can". Say "the code allows" and quote it.
5. Never say what staff have or have not decided before, or that no precedent exists.
6. Be concise and plain-spoken. You do not give legal advice or decide permits."""
CLOSED = {"SOURCES": "You have no documents, search or tools: answer only from what you already know.",
          "QUOTE": "Only quote words you are sure are the code's exact text."}
WEB = {"SOURCES": "You can search the web and open pages. Prefer the city's own published code and documents, "
                  "and check that what you rely on is the current edition.",
       "QUOTE": "Only quote words you have read on a page you opened, copied exactly."}
SYSTEM = {"bare": None, "rules": RULES.format(**CLOSED), "web": RULES.format(**WEB)}


def questions() -> list[dict]:
    out = []
    for f in QUESTION_FILES:
        out += [q for q in yaml.safe_load((ROOT / f).read_text()) if q.get("question")]
    return out


def ask(client, model: str, system: str | None, question: str, web: bool) -> dict:
    """One question, one answer. With web, Claude's server-side search and fetch run inside the call; a turn
    that pauses mid-search is sent back so it can finish."""
    msgs = [{"role": "user", "content": question}]
    kw = {"system": system} if system else {}
    if web:     # a paused turn is re-sent with everything read so far; caching makes that re-read cheap
        kw |= {"tools": WEB_TOOLS, "cache_control": {"type": "ephemeral"}}
    usage = dict.fromkeys(USAGE_KEYS, 0) | {"web_search_requests": 0, "calls": 0}
    blocks = []
    for _ in range(MAX_RESUMES + 1):
        r = client.messages.create(model=model, max_tokens=2000, messages=msgs, **kw)
        usage["calls"] += 1
        for k in USAGE_KEYS:
            usage[k] += getattr(r.usage, k, 0) or 0
        stu = getattr(r.usage, "server_tool_use", None)
        usage["web_search_requests"] += (getattr(stu, "web_search_requests", 0) or 0) if stu else 0
        blocks += r.content
        if r.stop_reason != "pause_turn":
            break
        msgs = msgs + [{"role": "assistant", "content": r.content}]
    out = {"answer": "".join(b.text for b in blocks if b.type == "text"), "stop_reason": r.stop_reason,
           "usage": usage}
    if web:
        out["searched"] = [(b.input or {}).get("query") for b in blocks
                           if b.type == "server_tool_use" and b.name == "web_search"]
        out["opened"] = [(b.input or {}).get("url") for b in blocks
                         if b.type == "server_tool_use" and b.name == "web_fetch"]
        out["cited_urls"] = sorted({c.url for b in blocks if b.type == "text"
                                    for c in (getattr(b, "citations", None) or []) if getattr(c, "url", None)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--condition", choices=("bare", "rules", "web"), default="rules")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--limit", type=int, help="only the first N questions (to try it out)")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt and questions; call nothing")
    a = ap.parse_args()

    qs = questions()[: a.limit]
    out = ROOT / "evals" / "runs" / f"baseline-{a.condition}-{a.model}.jsonl"
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()] if out.exists() else []
    config = CONFIG.get(a.condition, {})
    stale = [r["id"] for r in rows if r.get("config", {}) != config]
    if stale:
        print(f"Asking {len(stale)} questions again: they were answered with different settings.")
    rows = [r for r in rows if not r.get("error") and r.get("config", {}) == config]  # failed or stale: ask again
    if out.exists():
        out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    done = {r["id"] for r in rows}
    todo = [q for q in qs if q["id"] not in done]
    system = SYSTEM[a.condition]

    print(f"{len(qs)} questions, {len(done & {q['id'] for q in qs})} already answered, {len(todo)} to ask")
    print(f"model {a.model}, condition {a.condition}, output {out.relative_to(ROOT)}")
    if a.dry_run:
        print("\nSystem prompt:\n" + (system or "(none)") + "\n\nFirst question:\n" + (todo or qs)[0]["question"])
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")

    import anthropic
    client = anthropic.Anthropic()
    total = dict.fromkeys(USAGE_KEYS, 0) | {"web_search_requests": 0}
    with out.open("a") as fh:
        for i, q in enumerate(todo, 1):
            row = {"id": q["id"], "question": q["question"], "target": f"{a.model} ({a.condition})",
                   "condition": a.condition, "model": a.model, "config": config,
                   "asked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "answer": None, "error": None}
            try:
                row.update(ask(client, a.model, system, q["question"], web=a.condition == "web"))
                for k in total:
                    total[k] += row["usage"][k]
            except anthropic.APIError as e:
                row["error"] = f"{type(e).__name__}: {e}"
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"[{i}/{len(todo)}] {q['id']}: {'error' if row['error'] else 'ok'}")

    price = PRICE.get(a.model, (0, 0, 0, 0))
    cost = sum(total[k] * p for k, p in zip(USAGE_KEYS, price)) / 1e6 + total["web_search_requests"] * SEARCH_PRICE
    print(f"\nTokens: {total['input_tokens']} in, {total['output_tokens']} out, "
          f"{total['cache_read_input_tokens']} read from cache, {total['cache_creation_input_tokens']} written to cache, "
          f"{total['web_search_requests']} web searches. Cost about ${cost:.2f}"
          + ("" if a.model in PRICE else " (unknown model price)"))
    failed = [json.loads(l)["id"] for l in out.read_text().splitlines() if json.loads(l)["error"]]
    if failed:
        print(f"Errors on {failed}. Run the same command again to retry just those.")


if __name__ == "__main__":
    main()
