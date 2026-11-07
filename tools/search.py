#!/usr/bin/env python3
"""Search Plinth's knowledge lake. No dependencies beyond the standard library.

  search.py "front setback for a garage"          ranked passages (BM25), best first
  search.py "window replacement" --authority staff only staff precedent
  search.py "ADU height" --source ch17 -k 5        limit to one source, top 5
  search.py section 17.20.040                      print one section in full
  search.py list ch17                              list a source's sections
  search.py "..." --json                           machine-readable output for agents

Every result carries a citation, an authority (binding / official / staff) and the file path,
so an answer can quote the source and an agent can open the full section.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "knowledge" / "index" / "chunks.jsonl"

TOKEN = re.compile(r"\d+[a-z]?(?:\.\d+[a-z]?)+|[a-z0-9]+")
SECTION_NUM = re.compile(r"\b\d{1,2}[A-Za-z]?\.\d{1,3}[A-Za-z]?(?:\.\d{1,3}[A-Za-z]?)?\b")
STOP = set("a an and are as at be by can for from has have how i if in is it its may of on or our that the "
           "their this to was we what when where which will with would you your do does my".split())
AUTH_WEIGHT = {"binding": 1.0, "official": 0.95, "staff": 0.9}


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def load() -> list[dict]:
    if not CHUNKS.exists():
        sys.exit("No index yet. Run: python tools/ingest.py all   (or: python tools/ingest.py index)")
    return [json.loads(l) for l in CHUNKS.open()]


class BM25:
    def __init__(self, docs: list[dict], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = []
        df: Counter = Counter()
        for d in docs:
            # Title and citation count twice: a match there is a strong signal.
            toks = tokens(f"{d.get('title') or ''} {d.get('cite') or ''} " * 2 + d["text"])
            c = Counter(toks)
            self.tf.append((c, len(toks)))
            df.update(c.keys())
        self.n = len(docs)
        self.avg = sum(l for _, l in self.tf) / max(self.n, 1)
        self.idf = {t: math.log(1 + (self.n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, q: list[str], i: int) -> float:
        c, length = self.tf[i]
        s = 0.0
        for t in q:
            f = c.get(t)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / self.avg))
        return s


def snippet(text: str, q: list[str], width: int = 360) -> str:
    low = text.lower()
    hits = [low.find(t) for t in q if low.find(t) >= 0]
    start = max(0, min(hits) - 80) if hits else 0
    s = " ".join(text[start:start + width].split())
    return ("…" if start else "") + s + ("…" if start + width < len(text) else "")


def search(query: str, k: int, source: str | None, authority: str | None, kind: str | None,
           include_superseded: bool) -> list[dict]:
    docs = load()
    keep = [d for d in docs
            if (not source or d["source_id"] == source)
            and (not authority or d["authority"] == authority)
            and (not kind or d["kind"] == kind)
            and (include_superseded or d.get("status") != "superseded")]
    q = tokens(query)
    bm = BM25(keep)
    wanted = {m.lower() for m in SECTION_NUM.findall(query)}
    results = []
    for i, d in enumerate(keep):
        s = bm.score(q, i)
        if wanted and (d.get("section") or "").lower() in wanted:
            s += 100  # an exact section number in the query wins
        if s > 0:
            results.append((s * AUTH_WEIGHT.get(d.get("authority"), 0.9), d))
    results.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for s, d in results:
        if d["doc_id"] in seen:  # one hit per section; open the file for the rest
            continue
        seen.add(d["doc_id"])
        out.append({**{k: d[k] for k in ("doc_id", "cite", "title", "authority", "kind", "effective",
                                           "status", "path")},
                    "score": round(s, 2), "snippet": snippet(d["text"], q)})
        if len(out) == k:
            break
    return out


def find_section(num: str) -> list[Path]:
    num = num.removeprefix("§").strip()
    return sorted((ROOT / "knowledge" / "sections").glob(f"*/{num}.md"))


def main() -> None:
    argv = sys.argv[1:]
    if argv[:1] == ["section"] and len(argv) >= 2:
        paths = find_section(argv[1])
        if not paths:
            sys.exit(f"No section {argv[1]} in the lake. Try: search.py \"{argv[1]}\"")
        for p in paths:
            print(f"== {p.relative_to(ROOT)}\n{p.read_text()}")
        return
    if argv[:1] == ["list"]:
        base = ROOT / "knowledge" / "sections"
        for d in sorted(base.iterdir()) if base.exists() else []:
            if len(argv) > 1 and d.name != argv[1]:
                continue
            files = sorted(d.glob("*.md"))
            print(f"{d.name}: {len(files)} sections")
            if len(argv) > 1:
                for f in files:
                    title = next((l[7:].strip() for l in f.open() if l.startswith("title: ")), "")
                    print(f"  {f.stem:<14} {title}")
        return

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=8, help="number of results (default 8)")
    ap.add_argument("--source", help="limit to a source id, e.g. ch17")
    ap.add_argument("--authority", choices=["binding", "official", "staff"])
    ap.add_argument("--kind", choices=["code", "charter", "policy", "guideline", "form", "precedent"])
    ap.add_argument("--include-superseded", action="store_true", help="also show superseded staff answers")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    res = search(a.query, a.k, a.source, a.authority, a.kind, a.include_superseded)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    if not res:
        print("No matches. Nothing in the lake supports an answer; treat this as 'needs staff'.")
        return
    for i, r in enumerate(res, 1):
        flag = " [SUPERSEDED]" if r["status"] == "superseded" else ""
        eff = f", {r['effective']}" if r.get("effective") else ""
        title = "" if not r["title"] or r["title"].lower() in r["cite"].lower() else " " + r["title"]
        print(f"{i}. {r['cite']}{title}{flag}\n   {r['authority']}{eff} · {r['path']}\n   {r['snippet']}\n")


if __name__ == "__main__":
    main()
