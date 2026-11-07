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


# ---- parcel lookup, paste-to-fill
from app import parcel

FAKE_PARCEL = {"features": [{"attributes": {"PARNO": "050-3456-012-00", "ACRES": 0.2, "YEARBUILT": 1927, "BEDS": 0}}]}
GEO = {"matchedAddress": "21 PORTSMOUTH RD, PIEDMONT, CA, 94610", "coordinates": {"x": -122.23, "y": 37.82},
       "addressComponents": {"city": "PIEDMONT", "state": "CA", "zip": "94610"}}


def test_parcel_fills_only_returned_fields_with_source():
    rec = prop.build("x", GEO, fetch=lambda u: FAKE_PARCEL)
    f = rec["facts"]
    assert f["apn"]["value"] == "050-3456-012-00" and "UCD_Parcels" in f["apn"]["source"]
    assert f["lot_size"]["value"].startswith("8,712 sq ft") and f["year_built"]["value"] == "1927"
    assert f["bedrooms"]["value"] == "" and f["zone"]["value"] == ""  # not returned -> blank, not guessed


def test_parcel_failure_is_soft():
    def boom(u):
        raise OSError("blocked")
    rec = prop.build("x", GEO, fetch=boom)
    assert rec["facts"]["apn"]["value"] == "" and len(rec["parcel_notes"]) >= 1


def test_edit_changes_source_only_when_value_changes():
    rec = prop.build("x", GEO, fetch=lambda u: FAKE_PARCEL)
    prop.update_facts(rec, {"apn": "050-3456-012-00", "year_built": "1930"})
    assert "UCD" in rec["facts"]["apn"]["source"] and rec["facts"]["year_built"]["source"] == "entered by owner"


def test_paste_extraction_drops_ungrounded_values():
    text = "Built in 1927. Lot size: 8,700 sq ft. 3 bed / 2 bath."
    stub = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(content=[
        {"type": "tool_use", "id": "x", "name": "record_facts",
         "input": {"year_built": "1927", "lot_size": "8,700 sq ft", "zone": "A", "bedrooms": "3"}}])))
    facts, dropped = agent.extract_property_facts(text, client=stub)
    assert facts == {"year_built": "1927", "lot_size": "8,700 sq ft", "bedrooms": "3"} and dropped == ["zone"]


def test_paste_endpoint(monkeypatch):
    from app.main import app
    monkeypatch.setattr(agent, "extract_property_facts", lambda t, client=None: ({"year_built": "1927"}, ["zone"]))
    monkeypatch.setattr(prop, "geocode", lambda a, timeout=10: GEO)
    monkeypatch.setattr(parcel, "_get", lambda u, timeout=10: {"features": []})
    c = TestClient(app)
    h = {"x-session": c.post("/api/session").json()["session"]}
    assert c.post("/api/property/paste", headers=h, json={"text": "x"}).status_code == 400  # no property yet
    c.post("/api/property", headers=h, json={"address": "21 Portsmouth Rd"})
    r = c.post("/api/property/paste", headers=h, json={"text": "Built 1927"}).json()
    assert r["property"]["facts"]["year_built"]["source"] == "entered by owner (pasted text)"
    assert r["dropped"] == ["zone"]


def test_grounding_rules():
    g = agent._grounded
    assert not g("zone", "A", "A charming home with 3 bath")
    assert g("zone", "A", "Zoning: Zone A, single family")
    assert not g("bedrooms", "3", "built 1930, 2,300 sq ft")
    assert g("bedrooms", "3", "3 bed / 2 bath")
    assert g("lot_size", "8,700 sq ft", "Lot: 8700 sq ft")


def test_password_gate_and_rate_limit(monkeypatch):
    import base64
    from app import main
    c = TestClient(main.app)
    monkeypatch.setenv("PLINTH_PASSWORD", "s3cret")
    assert c.get("/").status_code == 401
    assert c.get("/healthz").status_code == 200
    good = {"authorization": "Basic " + base64.b64encode(b"anyone:s3cret").decode()}
    bad = {"authorization": "Basic " + base64.b64encode(b"anyone:nope").decode()}
    assert c.get("/", headers=bad).status_code == 401
    assert c.get("/", headers=good).status_code == 200
    monkeypatch.setattr(main, "LLM_LIMIT", 2)
    main._calls.clear()
    h = {**good, "x-session": c.post("/api/session", headers=good).json()["session"]}
    codes = [c.post("/api/chat", headers=h, json={"message": "hi"}).status_code for _ in range(3)]
    assert codes[-1] == 429 and 429 not in codes[:2]


# ---- address suggestions
from app import suggest as sg

PHOTON = {"features": [
    {"properties": {"housenumber": "21", "street": "Portsmouth Road", "city": "Piedmont", "postcode": "94610"}},
    {"properties": {"housenumber": "21", "street": "Portsmouth Road", "city": "Piedmont", "postcode": "94610"}},  # dupe
    {"properties": {"street": "Portsmouth Road", "city": "Piedmont", "postcode": "94610"}},      # no number
    {"properties": {"housenumber": "21", "street": "Portsmouth Ave", "city": "Oakland"}},         # wrong city
    {"properties": {"name": "Cafe", "city": "Piedmont"}}]}                                          # no street


def test_suggest_formats_filters_and_dedupes():
    sg._cache.clear()
    assert sg.suggest("21 Ports", fetch=lambda q: PHOTON) == ["21 Portsmouth Road, Piedmont, CA 94610"]
    sg._cache.clear()
    assert sg.suggest("Portsmouth", fetch=lambda q: PHOTON)[:2] == [
        "21 Portsmouth Road, Piedmont, CA 94610", "Portsmouth Road, Piedmont, CA 94610"]


def test_suggest_short_fail_soft_and_cache():
    sg._cache.clear()
    assert sg.suggest("ab", fetch=lambda q: 1 / 0) == []
    def boom(q):
        raise OSError("down")
    assert sg.suggest("21 Ports", fetch=boom) == []
    calls = []
    def ok(q):
        calls.append(q)
        return PHOTON
    sg.suggest("21 Ports", fetch=ok)
    sg.suggest("21  PORTS ", fetch=ok)  # same after normalising -> cached
    assert len(calls) == 1 and "Piedmont" in calls[0]


def test_suggest_endpoint_gate_and_limit(monkeypatch):
    from app import main
    c = TestClient(main.app)
    sid = c.post("/api/session").json()["session"]
    h = {"x-session": sid}
    monkeypatch.setattr(sg, "_fetch", lambda q, timeout=4: PHOTON)
    sg._cache.clear()
    assert c.get("/api/suggest?q=21 Ports", headers=h).json()["suggestions"] == ["21 Portsmouth Road, Piedmont, CA 94610"]
    assert c.get("/api/suggest?q=21 Ports").status_code == 400  # needs a session
    monkeypatch.setattr(main, "SUGGEST_LIMIT", 1)
    main._calls.clear()
    assert c.get("/api/suggest?q=21 Ports", headers=h).status_code == 200
    assert c.get("/api/suggest?q=21 Ports", headers=h).status_code == 429
