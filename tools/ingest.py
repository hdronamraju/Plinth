#!/usr/bin/env python3
"""Build Plinth's knowledge lake from the sources in knowledge/sources.yaml.

Pipeline (each step can be run alone; `all` runs them in order):

  fetch     download each source to knowledge/raw/<kind>/<id>.pdf (skips files already present)
  add       register a PDF you already have:  ingest.py add ch17 ~/Downloads/chapter17.pdf
  extract   PDF -> knowledge/text/<id>.txt (plain text, page breaks as form feeds)
  sections  text -> knowledge/sections/<id>/<section>.md, one file per code section,
            with YAML front matter (source, section number, title, division, pages, URL)
  index     sections + precedent -> knowledge/index/chunks.jsonl and knowledge/index/CATALOG.md

Requires: Python 3.10+, PyYAML, and poppler's `pdftotext` (falls back to pypdf if missing).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KNOW = ROOT / "knowledge"
RAW = KNOW / "raw"
TEXT = KNOW / "text"
SECTIONS = KNOW / "sections"
PRECEDENT = KNOW / "precedent"
INDEX = KNOW / "index"
MANIFEST = RAW / "MANIFEST.json"

CHUNK_WORDS = 300
CHUNK_OVERLAP = 50


# ---------------------------------------------------------------- sources

def load_sources() -> dict[str, dict]:
    data = yaml.safe_load((KNOW / "sources.yaml").read_text())
    out = {}
    for s in data["sources"]:
        if s["id"] in out:
            sys.exit(f"duplicate source id in sources.yaml: {s['id']}")
        if s.get("effective") is not None:
            s["effective"] = str(s["effective"])
        out[s["id"]] = s
    return out


def raw_path(src: dict) -> Path:
    return RAW / src["kind"] / f"{src['id']}.pdf"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(dict(sorted(m.items())), indent=2) + "\n")


def record(manifest: dict, src: dict, path: Path, how: str) -> None:
    data = path.read_bytes()
    manifest[src["id"]] = {
        "file": str(path.relative_to(KNOW)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "obtained": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "how": how,
        "url": src["url"],
    }


# ---------------------------------------------------------------- fetch / add

def quote_url(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(p._replace(path=urllib.parse.quote(urllib.parse.unquote(p.path))))


def cmd_fetch(ids: list[str], force: bool) -> None:
    sources, manifest = load_sources(), load_manifest()
    failed = []
    for sid in ids or sources:
        src = sources[sid]
        dest = raw_path(src)
        if dest.exists() and not force:
            print(f"skip   {sid} (have {dest.relative_to(ROOT)})")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(quote_url(src["url"]), headers={"User-Agent": "plinth-ingest/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
        except Exception as e:  # noqa: BLE001 - report and continue with the rest
            print(f"FAIL   {sid}: {e}")
            failed.append(sid)
            continue
        if not body.startswith(b"%PDF"):
            print(f"FAIL   {sid}: response is not a PDF ({len(body)} bytes)")
            failed.append(sid)
            continue
        dest.write_bytes(body)
        record(manifest, src, dest, "fetched")
        print(f"got    {sid} ({len(body):,} bytes)")
    save_manifest(manifest)
    if failed:
        print(f"\n{len(failed)} failed: {' '.join(failed)}")


def cmd_add(sid: str, file: str) -> None:
    sources, manifest = load_sources(), load_manifest()
    if sid not in sources:
        sys.exit(f"unknown source id {sid!r}; add it to knowledge/sources.yaml first")
    src = sources[sid]
    path = Path(file).expanduser()
    if not path.read_bytes()[:4] == b"%PDF":
        sys.exit(f"{path} is not a PDF")
    dest = raw_path(src)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, dest)
    record(manifest, src, dest, "added by hand")
    save_manifest(manifest)
    print(f"added  {sid} -> {dest.relative_to(ROOT)}")


# ---------------------------------------------------------------- extract

def pdf_to_text(pdf: Path) -> str:
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
                             capture_output=True, check=True)
        return out.stdout.decode("utf-8", "replace")
    from pypdf import PdfReader  # fallback
    return "\f".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)


def cmd_extract(ids: list[str]) -> None:
    sources = load_sources()
    TEXT.mkdir(parents=True, exist_ok=True)
    for sid in ids or sources:
        pdf = raw_path(sources[sid])
        if not pdf.exists():
            continue
        text = pdf_to_text(pdf)
        (TEXT / f"{sid}.txt").write_text(text)
        print(f"text   {sid}: {text.count(chr(12)) + 1} pages, {len(text.split()):,} words")


# ---------------------------------------------------------------- sections

# "17.20.040 Development standards."  "Section 1.01 Name."  "Sec. 8.12 Permits required."
HEAD = re.compile(
    r"^\s*(?:Sec(?:tion)?\.?\s+)?"
    r"(?P<num>\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?(?:\.\d{1,3}[A-Z]?)?)\.?\s+"
    r"(?P<title>[A-Z][^\n]{0,160}?\.)(?=\s|$)(?P<rest>.*)$"
)
DIVISION = re.compile(r"^\s*(DIVISION|ARTICLE|PART)\s+(?P<num>[\dA-Z.]+)\.?\s*(?P<title>.*)$", re.I)
TOC_LINE = re.compile(r"^\s*(?:Sections:\s*|\d{1,2}[A-Z]?\.\d{1,3}[A-Z]?(?:\.\d{1,3}[A-Z]?)?\s+[A-Z][^.]{0,120})$")
PAGE_NO = re.compile(r"^\s*(?:\d+[A-Z]?\s*-\s*\d+|Page \d+( of \d+)?|\d+)\s*$")


def sort_key(num: str) -> tuple:
    parts = []
    for p in num.split("."):
        m = re.match(r"(\d+)([A-Z]?)", p)
        parts.append((int(m.group(1)), m.group(2)) if m else (0, p))
    return tuple(parts)


def strip_running_heads(pages: list[str]) -> list[list[str]]:
    """Remove page numbers and lines that repeat at the top or bottom of many pages."""
    edge = Counter()
    split = [p.splitlines() for p in pages]
    for lines in split:
        body = [l.strip() for l in lines if l.strip()]
        for l in set(body[:3] + body[-3:]):
            edge[l] += 1
    repeated = {l for l, n in edge.items() if len(pages) >= 4 and n >= max(3, len(pages) * 0.3)}
    return [[l for l in lines if l.strip() not in repeated and not PAGE_NO.match(l)] for lines in split]


def clean(lines: list[str]) -> str:
    """Dedent, drop trailing spaces, collapse runs of blank lines."""
    lines = [l.rstrip() for l in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    indents = [len(l) - len(l.lstrip()) for l in lines if l.strip()]
    cut = min(indents) if indents else 0
    out, blank = [], 0
    for l in lines:
        if not l.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(l[cut:])
    return "\n".join(out)


def parse_sections(text: str) -> list[dict]:
    """Split one source's text into sections.

    A heading is a section number followed by a title that ends in a period. Table-of-contents
    lines ("17.66.010 Intent") have no period and are skipped. A heading whose number goes
    backwards is treated as a cross-reference inside the body, not a new section.
    """
    pages = strip_running_heads(text.split("\f"))
    sections: list[dict] = []
    division = None
    current = None
    last_key = None
    for page_no, lines in enumerate(pages, start=1):
        for line in lines:
            d = DIVISION.match(line)
            if d and d.group("title").strip() and len(line.strip()) < 120:
                division = f"{d.group(1).title()} {d.group('num').rstrip('.')} {d.group('title').strip()}".strip()
                continue
            m = HEAD.match(line)
            if m:
                key = sort_key(m.group("num"))
                if last_key is None or key > last_key:
                    current = {
                        "section": m.group("num"),
                        "title": m.group("title").strip().rstrip("."),
                        "division": division,
                        "pages": [page_no],
                        "lines": [m.group("rest").strip()] if m.group("rest").strip() else [],
                    }
                    sections.append(current)
                    last_key = key
                    continue
            if TOC_LINE.match(line):
                continue  # a division's table of contents, not body text
            if current is not None:
                current["lines"].append(line)
                if current["pages"][-1] != page_no:
                    current["pages"].append(page_no)
    for s in sections:
        s["body"] = clean(s.pop("lines"))
    return [s for s in sections if s["body"]]


def page_chunks(text: str) -> list[dict]:
    """Fallback for documents without numbered sections: one record per page."""
    out = []
    for i, lines in enumerate(strip_running_heads(text.split("\f")), start=1):
        body = clean(lines)
        if body:
            out.append({"section": f"p{i:03d}", "title": f"Page {i}", "division": None,
                        "pages": [i], "body": body})
    return out


def front_matter(d: dict) -> str:
    return "---\n" + yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=1000) + "---\n"


def citation(src: dict, section: str | None) -> str:
    if src["kind"] in ("code", "charter") and section and not section.startswith("p"):
        prefix = "Piedmont City Charter §" if src["kind"] == "charter" else "Piedmont City Code §"
        return prefix + section
    page = f", p. {section[1:].lstrip('0')}" if section and section.startswith("p") else ""
    return f"{src['title']}{page}"


def cmd_sections(ids: list[str]) -> None:
    sources = load_sources()
    for sid in ids or sources:
        txt = TEXT / f"{sid}.txt"
        if not txt.exists():
            continue
        src = sources[sid]
        text = txt.read_text()
        secs = parse_sections(text) if src["kind"] in ("code", "charter") else []
        mode = "sections"
        if len(secs) < 3:
            secs, mode = page_chunks(text), "pages"
        out_dir = SECTIONS / sid
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        for s in secs:
            meta = {
                "id": f"{sid}:{s['section']}",
                "source_id": sid,
                "source_title": src["title"],
                "kind": src["kind"],
                "authority": src["authority"],
                "section": s["section"],
                "title": s["title"],
                "division": s["division"],
                "cite": citation(src, s["section"]),
                "effective": src.get("effective"),
                "pages": s["pages"],
                "source_url": src["url"],
            }
            heading = f"# {meta['cite']} {s['title']}" if mode == "sections" else f"# {src['title']}, {s['title']}"
            (out_dir / f"{s['section']}.md").write_text(front_matter(meta) + "\n" + heading + "\n\n" + s["body"] + "\n")
        print(f"split  {sid}: {len(secs)} {mode}")


# ---------------------------------------------------------------- index

def read_md(path: Path) -> tuple[dict, str]:
    raw = path.read_text()
    if not raw.startswith("---\n"):
        return {}, raw
    _, fm, body = raw.split("---\n", 2)
    return yaml.safe_load(fm) or {}, body.strip()


def chunk_words(text: str) -> list[str]:
    words = text.split()
    if len(words) <= CHUNK_WORDS + CHUNK_OVERLAP:
        return [text]
    out, i = [], 0
    while i < len(words):
        out.append(" ".join(words[i:i + CHUNK_WORDS]))
        i += CHUNK_WORDS - CHUNK_OVERLAP
    return out


def cmd_index() -> None:
    INDEX.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    docs = []
    for path in sorted(SECTIONS.glob("*/*.md")) + sorted(PRECEDENT.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        meta, body = read_md(path)
        if not meta:
            continue
        if meta.get("topics"):
            body = "Topics: " + ", ".join(meta["topics"]) + "\n\n" + body
        docs.append((path, meta, body))

    n_chunks = 0
    with (INDEX / "chunks.jsonl").open("w") as f:
        for path, meta, body in docs:
            parts = chunk_words(body)
            for i, part in enumerate(parts):
                rec = {
                    "chunk_id": f"{meta['id']}#{i}" if len(parts) > 1 else meta["id"],
                    "doc_id": meta["id"],
                    "path": str(path.relative_to(ROOT)),
                    "kind": meta.get("kind"),
                    "authority": meta.get("authority"),
                    "source_id": meta.get("source_id"),
                    "section": meta.get("section"),
                    "title": meta.get("title"),
                    "cite": meta.get("cite"),
                    "effective": str(meta.get("effective") or meta.get("answered_on") or "") or None,
                    "status": meta.get("status", "current"),
                    "text": part,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_chunks += 1

    # A table of contents an agent can read in one pass to know what exists and where.
    by_source: dict[str, list] = {}
    for path, meta, _ in docs:
        by_source.setdefault(meta.get("source_id") or "precedent", []).append((path, meta))
    lines = [
        "# Knowledge lake catalog",
        "",
        "Generated by `tools/ingest.py index`. Do not edit by hand.",
        "",
        f"{len(docs)} documents, {n_chunks} search chunks.",
        "",
    ]
    for sid, items in sorted(by_source.items(), key=lambda kv: kv[0]):
        src = sources.get(sid)
        head = src["title"] if src else "Staff precedent"
        eff = f" (effective {src['effective']})" if src and src.get("effective") else ""
        lines += [f"## {head}{eff}", "", "| Section | Title | File |", "| --- | --- | --- |"]
        for path, meta in items:
            sec = meta.get("section") or meta["id"]
            title = (meta.get("title") or "").replace("|", "/")
            if meta.get("status") == "superseded":
                title += " (superseded)"
            lines.append(f"| {sec} | {title} | [{path.name}]({path.relative_to(INDEX.parent.parent).as_posix()}) |")
        lines.append("")
    missing = [s for s in sources if not (SECTIONS / s).exists()]
    if missing:
        lines += ["## Not yet ingested", "", "Listed in `sources.yaml` but no text yet: " + ", ".join(missing), ""]
    (INDEX / "CATALOG.md").write_text("\n".join(lines))
    # Paths in CATALOG.md are relative to the repo root's knowledge/.. so fix them to be relative to index/.
    cat = (INDEX / "CATALOG.md").read_text().replace("](knowledge/", "](../")
    (INDEX / "CATALOG.md").write_text(cat)
    print(f"index  {len(docs)} documents, {n_chunks} chunks -> knowledge/index/")


# ---------------------------------------------------------------- cli

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "extract", "sections", "all"):
        p = sub.add_parser(name)
        p.add_argument("ids", nargs="*", help="source ids (default: all)")
        if name in ("fetch", "all"):
            p.add_argument("--force", action="store_true", help="re-download files already present")
    p = sub.add_parser("add")
    p.add_argument("id")
    p.add_argument("file")
    sub.add_parser("index")
    a = ap.parse_args()

    if a.cmd == "fetch":
        cmd_fetch(a.ids, a.force)
    elif a.cmd == "add":
        cmd_add(a.id, a.file)
    elif a.cmd == "extract":
        cmd_extract(a.ids)
    elif a.cmd == "sections":
        cmd_sections(a.ids)
    elif a.cmd == "index":
        cmd_index()
    elif a.cmd == "all":
        cmd_fetch(a.ids, a.force)
        cmd_extract(a.ids)
        cmd_sections(a.ids)
        cmd_index()


if __name__ == "__main__":
    main()
