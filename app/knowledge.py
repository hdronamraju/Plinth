"""Thin wrapper over tools/search.py for the app and agent.

Adds what the raw index lacks: precedent scope/status/answered_on (read from front matter),
and a record of every passage returned so answers can be checked against it.
"""
from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import search as _search  # noqa: E402

MAX_PAGE_RUN = 6  # most pages one get_section("source:pNNN-pNNN") call may return
CODE_EDITION = "Piedmont City Code Chapter 17, effective 2026-05-20"
LABEL = {"binding": "Code says", "official": "City policy says", "staff": "Staff have said"}


def front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, text


@lru_cache(maxsize=1)
def _index_ok() -> bool:
    return _search.CHUNKS.exists()


def search(query: str, source: str | None = None, authority: str | None = None, k: int = 6,
           property_address: str | None = None, also: list[str] | None = None) -> list[dict]:
    """Ranked passages. Superseded precedent is hidden; this_property precedent only shown
    for the matching address."""
    if not _index_ok():
        return []
    hits = _search.search(query, k * 2, source, authority, None, False, also)
    out = []
    for h in hits:
        h = dict(h)
        h["label"] = LABEL.get(h["authority"], "Source says")
        if h["kind"] == "precedent":
            fm, _ = front_matter(ROOT / h["path"])
            h.update(scope=fm.get("scope"), answered_on=str(fm.get("answered_on")),
                     pending=fm.get("pending", False), property=fm.get("property"))
            if h["scope"] == "this_property" and (
                    not property_address or
                    str(fm.get("property", "")).lower().split(",")[0] not in property_address.lower()):
                continue
        out.append(h)
        if len(out) == k:
            break
    return out


def _find(number: str) -> list[Path]:
    """Code section (17.20.040), or a document page: "design-guidelines:p022" (a bare "p022" is ambiguous)."""
    number = number.strip().removeprefix("§")
    if ":" in number:
        src, page = (x.strip() for x in number.split(":", 1))
        if re.fullmatch(r"[\w.-]+", src) and re.fullmatch(r"p\d{3}", page):
            return sorted((ROOT / "knowledge" / "sections").glob(f"{src}/{page}.md"))
    m = re.fullmatch(r"([\w.-]+):p(\d{3})-p(\d{3})", number)     # a run of pages: design-guidelines:p018-p022
    if m:
        first, last = int(m.group(2)), int(m.group(3))
        if not (0 < first <= last and last - first < MAX_PAGE_RUN):
            return []
        base = ROOT / "knowledge" / "sections"
        return [p for n in range(first, last + 1) for p in sorted(base.glob(f"{m.group(1)}/p{n:03d}.md"))]
    if re.fullmatch(r"p\d{3}", number):      # a bare page id matches dozens of sources: name the source
        return []
    return _search.find_section(number)


def neighbors(doc_id: str) -> dict:
    """For a page document (e.g. design-guidelines:p018) the ids of the pages before and after it, so a list
    or table that continues across pages can be followed."""
    m = re.fullmatch(r"([\w.-]+):p(\d{3})", doc_id or "")
    if not m:
        return {}
    src, n = m.group(1), int(m.group(2))
    base = ROOT / "knowledge" / "sections" / src
    out = {}
    for key, num in (("prev_page", n - 1), ("next_page", n + 1)):
        if num > 0 and (base / f"p{num:03d}.md").exists():
            out[key] = f"{src}:p{num:03d}"
    return out


def get_section(number: str) -> list[dict]:
    res = []
    for p in _find(number):
        fm, body = front_matter(p)
        res.append({"doc_id": fm.get("id"), "cite": fm.get("cite"), "authority": fm.get("authority"),
                    "effective": str(fm.get("effective")) if fm.get("effective") else None,
                    "label": LABEL.get(fm.get("authority"), "Source says"), "text": body})
    return res


def zone_section(zone: str) -> str | None:
    """Zone letter -> its regulations section number, if the lake has it."""
    z = zone.strip().upper().removeprefix("ZONE ").strip()
    n = {"A": "17.20.040", "B": "17.22.040", "C": "17.24.040", "D": "17.26.040", "E": "17.28.040"}.get(z)
    return n if n and _search.find_section(n) else None


def catalog() -> dict:
    """What the knowledge base holds: sources that are searchable now, and sources the city publishes that are
    in the manifest but not loaded. Built from sources.yaml, covers.yaml and the sections folder."""
    base = ROOT / "knowledge"
    try:
        sources = (yaml.safe_load((base / "sources.yaml").read_text()) or {}).get("sources", [])
        covers = yaml.safe_load((base / "covers.yaml").read_text()) or {}
    except OSError:
        return {"available": [], "not_available": []}
    available, missing = [], []
    for s in sources:
        folder = base / "sections" / s["id"]
        n = len(list(folder.glob("*.md"))) if folder.is_dir() else 0
        if n == 0:
            missing.append({"id": s["id"], "title": s["title"]})
            continue
        available.append({"id": s["id"], "title": s["title"], "kind": s["kind"], "authority": s["authority"],
                          "effective": str(s["effective"]) if s.get("effective") else None,
                          "documents": n, "covers": covers.get(s["id"]),
                          "reference": bool(s.get("reference"))})
    return {"available": available, "not_available": missing}


def catalog_text() -> str:
    """The catalog as a compact block for the system prompt."""
    c = catalog()
    detailed = [s for s in c["available"] if s["covers"]]
    plain = [s for s in c["available"] if not s["covers"] and not s["reference"]]
    named_only = [s for s in c["available"] if s["reference"]]
    lines = ["KNOWLEDGE BASE (everything you can search; pass an id as `source` to search one document set):"]
    for s in detailed:
        eff = f", effective {s['effective']}" if s["effective"] else ""
        lines.append(f"- {s['id']}: {s['title']}{eff}. {s['covers']}")
    if plain:
        lines.append("- Other documents searched by default: " + "; ".join(f"{s['id']} {s['title']}" for s in plain) + ".")
    if named_only:
        lines.append("- Other city documents, searched ONLY when you name the id as `source` (they are left out of "
                     "ordinary searches): " + "; ".join(f"{s['id']} {s['title']}" for s in named_only) + ".")
    if c["not_available"]:
        lines.append("Published by the city but NOT loaded (say so and mark Needs staff if a question depends on them): "
                     + "; ".join(f"{s['id']} {s['title']}" for s in c["not_available"]) + ".")
    return "\n".join(lines)
