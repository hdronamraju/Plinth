"""App tests. No network and no API key needed (Anthropic client is stubbed)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pypdf
import pytest
from starlette.testclient import TestClient

from app import agent, knowledge, store
from app import property as prop


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DIR", tmp_path)


def test_search_finds_code_and_abstains():
    hits = knowledge.search("Zone A minimum lot area lot coverage", k=5)
    assert any("17.20.040" in h["cite"] for h in hits)
    assert knowledge.search("zzzz qqqq xxyy") == []


def test_superseded_precedent_hidden():
    hits = knowledge.search("garage over property line convert", authority="staff", k=10)
    assert all(h["status"] != "superseded" for h in hits)


def test_this_property_precedent_needs_matching_address():
    for h in knowledge.search("window replacement", authority="staff", k=10, property_address="5 Elm St, Piedmont"):
        assert h.get("scope") != "this_property"


def test_zone_lookup_quotes_code():
    rec = prop.build("21 Lorita Ave", use_geocoder=False)
    assert rec["warnings"] and rec["facts"]["zone"]["source"] == "entered by owner"
    assert prop.zone_info(rec) is None
    prop.update_facts(rec, {"zone": "A"})
    z = prop.zone_info(rec)
    assert z["section"] == "17.20.040" and "Zone A requirements" in z["text"]


def test_geocode_mock_piedmont_check():
    geo = {"matchedAddress": "21 LORITA AVE, PIEDMONT, CA, 94611", "coordinates": {"x": -122.2, "y": 37.8},
           "addressComponents": {"city": "PIEDMONT", "state": "CA", "zip": "94611"}}
    assert not prop.build("x", geo)["warnings"]
    geo["addressComponents"]["city"] = "OAKLAND"
    geo["addressComponents"]["zip"] = "94601"
    assert "not appear to be in Piedmont" in prop.build("x", geo)["warnings"][0]


def test_verify_quotes_strips_fabrication():
    real = knowledge.get_section("17.20.040")[0]["text"]
    good = "> Minimum 8,000 square feet, subject to exception"
    out, bad = agent.verify_quotes(good + "\n> The city shall approve everything", [real])
    assert bad == 1 and good in out and "shall approve" not in out


def _state_with_questions():
    st = {"property": prop.build("21 Lorita Ave, Piedmont, CA", use_geocoder=False), "staff_questions": [],
          "messages": [], "pdfs": []}
    st["staff_questions"] = [
        {"id": "sq1", "title": "Garage FAR", "question": "Does the garage footprint count toward floor area?",
         "context": "Garage crosses the line.", "code_refs": ["17.90.020"], "proposed_reading": "Whole footprint counts."},
        {"id": "sq2", "title": "Odd thing", "question": "Zzzz qqqq?", "context": "", "code_refs": ["99.99.999"],
         "proposed_reading": "Unsure."}]
    return st


def test_pdf_fields_and_roundtrip():
    st = _state_with_questions()
    r = agent.make_pdf(st, "Rebuild garage.")
    assert r["ok"]
    rd = pypdf.PdfReader(store.DIR / r["file"])
    names = set(rd.get_fields())
    assert {"q1_decision", "q1_notes", "q1_section", "q2_decision", "reviewer_name", "reviewer_date"} <= names
    meta = json.loads(rd.metadata.subject)
    assert meta["questions"] == {"q1": "sq1", "q2": "sq2"} and meta["plinth_doc_id"] == r["doc_id"]
    text = "".join(p.extract_text() for p in rd.pages)
    assert "No section found in the knowledge base" in text  # q2 abstains
    assert "Prepared with Plinth. Not an application or permit." in text
    assert "approved" not in text.lower().replace("not approved", "")
    # fill + re-read
    w = pypdf.PdfWriter(clone_from=rd)
    w.update_page_form_field_values(w.pages[1], {"q1_notes": "Agree."}, auto_regenerate=False)
    assert pypdf.PdfReader(__import__("io").BytesIO(_save(w))).get_fields()["q1_notes"].get("/V") == "Agree."
    st2 = agent.make_pdf(st)  # second export bumps version
    assert st2["version"] == 2 and st2["doc_id"] == r["doc_id"]


def _save(w):
    import io
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


class Stub:
    """Scripted Anthropic client: search -> add question -> final answer with one real, one fake quote."""
    def __init__(self, final):
        self.script = [
            [{"type": "tool_use", "id": "t1", "name": "get_section", "input": {"number": "17.20.040"}}],
            [{"type": "tool_use", "id": "t2", "name": "add_staff_question",
              "input": {"title": "T", "question": "Q?", "proposed_reading": "P", "code_refs": ["17.20.040"]}}],
            [{"type": "text", "text": final}]]
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        return SimpleNamespace(content=[SimpleNamespace(**b, model_dump=(lambda b=b: b)) for b in self.script.pop(0)])


def test_agent_loop_with_stub():
    final = "**Code says**\n> Minimum 8,000 square feet\n> Totally invented rule\n"
    r = agent.chat("sess123456", "lot size?", client=Stub(final))
    assert "Minimum 8,000 square feet" in r["answer"] and "invented" not in r["answer"]
    assert r["notes"] and len(r["staff_questions"]) == 1
    assert store.load("sess123456")["messages"]  # persisted


def test_missing_key_is_clear(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        agent.chat("sess123456", "hi")


def test_http_flow():
    from app.main import app
    c = TestClient(app)
    sid = c.post("/api/session").json()["session"]
    h = {"x-session": sid}
    assert c.get("/api/state").status_code == 400  # no session header
    assert c.get("/api/state", headers=h).json()["property"] is None
    assert c.post("/api/chat", headers=h, json={"message": "hi"}).status_code in (502, 503)
    assert c.get("/").status_code == 200
