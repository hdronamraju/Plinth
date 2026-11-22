"""Several wordings of one question are merged by reciprocal rank fusion; one wording is unchanged."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import search  # noqa: E402


def _row(doc_id, text, title="t"):
    return {"chunk_id": doc_id, "doc_id": doc_id, "path": "x", "kind": "code", "authority": "binding",
            "source_id": "s", "reference": False, "effective": None, "status": "current", "section": doc_id,
            "title": title, "cite": doc_id, "text": text}


def _index(tmp_path, monkeypatch):
    rows = [_row("a", "shed setback rear yard accessory structure"),
            _row("b", "garden outbuilding distance neighbor boundary line"),
            _row("c", "fence height permit street")]
    f = tmp_path / "chunks.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    monkeypatch.setattr(search, "CHUNKS", f)


def test_one_wording_misses_what_another_wording_finds(tmp_path, monkeypatch):
    _index(tmp_path, monkeypatch)
    single = [h["doc_id"] for h in search.search("shed", 5, None, None, None, False)]
    multi = [h["doc_id"] for h in search.search("shed", 5, None, None, None, False,
                                                ["outbuilding distance boundary line"])]
    assert "b" not in single and "b" in multi          # found only through the second wording
    assert multi.index("b") < len(multi)


def test_no_extra_wordings_is_identical_to_before(tmp_path, monkeypatch):
    _index(tmp_path, monkeypatch)
    a = search.search("shed setback", 5, None, None, None, False)
    assert a == search.search("shed setback", 5, None, None, None, False, None)
    assert a == search.search("shed setback", 5, None, None, None, False, [])
    assert a == search.search("shed setback", 5, None, None, None, False, ["", "   ", 5])   # junk is ignored


def test_at_most_three_extra_wordings_are_used(tmp_path, monkeypatch):
    _index(tmp_path, monkeypatch)
    many = ["fence", "fence", "fence", "outbuilding boundary"]       # the 4th is past the limit
    ids = [h["doc_id"] for h in search.search("shed", 5, None, None, None, False, many)]
    assert "b" not in ids
