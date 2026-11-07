"""Parser tests. Run: python -m pytest tests/  (or python tests/test_ingest.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from ingest import parse_sections, sort_key  # noqa: E402

# Shaped like the city's Chapter 17 PDF: running head + page number on every page,
# a division table of contents without periods, wrapped bodies, and an in-body cross-reference.
PAGE1 = """                         Planning & Land Use
DIVISION 17.20 ZONE A: SINGLE FAMILY RESIDENTIAL

Sections:
17.20.010 Purpose
17.20.040 Regulations

17.20.010 Purpose.
The purpose of Zone A is to preserve the single-family character
of the city.
                                 17-1
"""
PAGE2 = """                         Planning & Land Use
17.20.040 Regulations. The following standards apply in Zone A.
   A. Street yard setback: 20 feet.
   B. Side and rear yard setbacks: 5 feet.
17.06.030 Building permits. This cross-reference line must stay inside 17.20.040.
                                 17-2
"""
PAGE3 = """                         Planning & Land Use
DIVISION 17.90 DEFINITIONS AND MEASUREMENTS

Sections:
17.90.010 Definitions
17.90.020 Measurements

17.90.020 Measurements.
Floor area means the total area of all floors.
                                 17-3
"""
PAGE4 = """                         Planning & Land Use
Lot coverage is measured as the area covered by structures.
                                 17-4
"""
TEXT = "\f".join([PAGE1, PAGE2, PAGE3, PAGE4])


def test_sections_found_and_toc_skipped():
    secs = parse_sections(TEXT)
    assert [s["section"] for s in secs] == ["17.20.010", "17.20.040", "17.90.020"]


def test_titles_divisions_pages():
    s = {x["section"]: x for x in parse_sections(TEXT)}
    assert s["17.20.040"]["title"] == "Regulations"
    assert s["17.20.040"]["division"] == "Division 17.20 ZONE A: SINGLE FAMILY RESIDENTIAL"
    assert s["17.90.020"]["division"].startswith("Division 17.90")
    assert s["17.90.020"]["pages"] == [3, 4]


def test_body_keeps_text_and_drops_running_heads():
    s = {x["section"]: x for x in parse_sections(TEXT)}
    body = s["17.20.040"]["body"]
    assert body.startswith("The following standards apply in Zone A.")
    assert "Street yard setback: 20 feet." in body
    assert "17.06.030 Building permits" in body  # cross-reference stays in the body
    for sec in s.values():
        assert "Planning & Land Use" not in sec["body"]
        assert "17-1" not in sec["body"] and "17-4" not in sec["body"]
    assert "Lot coverage is measured" in s["17.90.020"]["body"]
    assert "Sections:" not in body and "17.90.010 Definitions" not in body  # next division's TOC


def test_sort_key_handles_letters():
    assert sort_key("17.20.040") < sort_key("17.90.020")
    assert sort_key("12.1") < sort_key("12A.1")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
