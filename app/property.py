"""Property record. Every fact is {value, source, as_of}. Geocoder facts come from the US Census;
everything else is owner-entered and labeled so. Zone is never guessed."""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request

from . import knowledge, parcel

GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
FIELDS = ["apn", "zone", "lot_size", "year_built", "building_sqft", "bedrooms", "bathrooms",
          "existing_structures", "easements", "permits_on_file"]
LABELS = {"apn": "APN", "zone": "Zone", "lot_size": "Lot size", "year_built": "Year built",
          "building_sqft": "Building size (sq ft)", "bedrooms": "Bedrooms", "bathrooms": "Bathrooms",
          "existing_structures": "Existing structures", "easements": "Easements / encroachments",
          "permits_on_file": "Permits / survey on file"}
PIEDMONT_ZIPS = {"94610", "94611", "94618"}
NOT_CONFIRMED = ("Not confirmed by records: easements, encroachments, unpermitted work and anything not "
                 "in the city's files may be missing here. Add what you know; staff can confirm.")


def fact(value, source, as_of=None):
    return {"value": value, "source": source, "as_of": as_of or dt.date.today().isoformat()}


def geocode(address: str, timeout: float = 10) -> dict | None:
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    try:
        with urllib.request.urlopen(f"{GEOCODER}?{q}", timeout=timeout) as r:
            data = json.load(r)
        m = data["result"]["addressMatches"]
    except Exception:
        return None
    return m[0] if m else None


def build(address: str, geo: dict | None = None, use_geocoder: bool = True, fetch=None) -> dict:
    geo = geo if geo is not None else (geocode(address) if use_geocoder else None)
    warnings = []
    if geo:
        comp = geo.get("addressComponents", {})
        in_piedmont = (comp.get("city", "").upper() == "PIEDMONT" or comp.get("zip") in PIEDMONT_ZIPS
                       ) and comp.get("state", "CA") == "CA"
        if not in_piedmont:
            warnings.append("This address does not appear to be in Piedmont, CA. Plinth only covers the "
                            "Piedmont planning code.")
        norm = geo["matchedAddress"].title().replace(", Ca,", ", CA,")
        coords = geo.get("coordinates", {})
        prop = {"address": fact(norm, "US Census Geocoder"),
                "latitude": fact(coords.get("y"), "US Census Geocoder"),
                "longitude": fact(coords.get("x"), "US Census Geocoder")}
    else:
        warnings.append("Could not verify this address with the Census geocoder (no match or no network). "
                        "Using the address as typed.")
        prop = {"address": fact(address.strip(), "entered by owner")}
    for f in FIELDS:
        prop[f] = fact("", "entered by owner")
    notes = []
    if geo and prop.get("latitude", {}).get("value") is not None:
        found, notes = parcel.lookup(prop["latitude"]["value"], prop["longitude"]["value"],
                                     **({"fetch": fetch} if fetch else {}))
        prop.update(found)
    return {"facts": prop, "warnings": warnings, "parcel_notes": notes, "not_confirmed": NOT_CONFIRMED,
            "confirmed": False}


def update_facts(record: dict, updates: dict, source: str = "entered by owner") -> dict:
    """Apply edits. Unchanged values keep their original source; changed values become owner-entered."""
    for k, v in updates.items():
        if k in FIELDS or k == "address":
            v = str(v).strip()
            if record["facts"].get(k, {}).get("value") != v:
                record["facts"][k] = fact(v, source)
    return record


def zone_info(record: dict) -> dict | None:
    """If the owner entered a zone, return its regulations section, quoted from the lake."""
    z = (record["facts"].get("zone") or {}).get("value", "")
    if not z:
        return None
    num = knowledge.zone_section(z)
    if not num:
        return {"zone": z, "section": None,
                "note": "No section for this zone is in the knowledge base. Needs staff."}
    sec = knowledge.get_section(num)[0]
    return {"zone": z, "section": num, "cite": sec["cite"], "label": sec["label"],
            "effective": sec["effective"], "text": sec["text"][:3500]}


def summary(record: dict) -> str:
    lines = []
    for k, v in record["facts"].items():
        if k in ("latitude", "longitude"):
            continue
        lines.append(f"{LABELS.get(k, k.title())}: {v['value'] or '(not provided)'} [{v['source']}, as of {v['as_of']}]")
    return "\n".join(lines)
