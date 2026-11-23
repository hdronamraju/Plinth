"""Parcel lookup for a Piedmont address, from Alameda County's public parcel layer.

The county layer is searched by street address (the Census geocoder puts its point on the street centerline,
which is outside the lot, so a point search finds nothing). If the address search finds no parcel, parcels within
COUNTY_RADIUS_M of the geocoded point are searched for one whose house number and street match. Nothing is
guessed: no match means nothing is filled. Every value is labeled with its source and date.

Only APN and lot size come from the county layer. It has no zone, year built or building data. The layer also
holds owner mailing addresses; those fields are never requested.

PLINTH_PARCEL_URL can name another ArcGIS layer to try afterwards by point (see tools/probe_parcel.py).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

COUNTY = {"name": "Alameda County parcel map",
          "url": "https://services5.arcgis.com/ROBnTHSNjoZ2Wm1P/arcgis/rest/services/Parcels/FeatureServer/0"}
COUNTY_FIELDS = "APN,PrintParcel,SitusAddress,SitusStreetNumber,SitusStreetName,SitusCity"  # never Mailing*
COUNTY_RADIUS_M = 40
FEET_SR = 2227  # California State Plane zone III, US feet: lot area comes out in square feet

# For other layers (PLINTH_PARCEL_URL): our field -> candidate attribute names (case-insensitive), first match wins
CANDIDATES = {
    "apn": ["APN", "APN_15", "PARNO", "PARCELID", "PARCEL_ID", "PARCEL", "PARCELNUMBER"],
    "acres": ["ACRES", "ACREAGE", "GIS_ACRES", "LOT_ACRES", "CALC_ACRES"],
    "lot_sqft": ["LOT_SQFT", "LOTSQFT", "LOT_SIZE", "LOTSIZE", "LOT_AREA", "LANDSQFT", "LAND_SQFT"],
    "year_built": ["YEAR_BUILT", "YEARBUILT", "YR_BUILT", "YRBUILT", "EFFYEAR", "EFF_YEAR"],
    "building_sqft": ["BLDG_SQFT", "BUILDING_SQFT", "BLDGSQFT", "LIVING_AREA", "SQFT", "IMPR_SQFT"],
    "bedrooms": ["BEDROOMS", "BEDS", "BED_ROOMS"],
    "bathrooms": ["BATHROOMS", "BATHS", "BATH_ROOMS"],
}


def providers() -> list[dict]:
    """Extra point-query layers, tried after the county layer."""
    custom = os.environ.get("PLINTH_PARCEL_URL")
    return [{"name": "Configured parcel service (PLINTH_PARCEL_URL)", "url": custom}] if custom else []


def _get(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def query_url(layer_url: str, lat: float, lon: float) -> str:
    q = urllib.parse.urlencode({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
                                "returnGeometry": "false", "f": "json"})
    return f"{layer_url.rstrip('/')}/query?{q}"


def split_street(line: str) -> tuple[str, str] | None:
    """'120 VISTA AVE, PIEDMONT, CA, 94611' -> ('120', 'VISTA AVE'). None if there is no house number."""
    m = re.match(r"\s*(\d+[A-Z]?)\s+([^,]+)", (line or "").upper())
    return (m.group(1), " ".join(m.group(2).split())) if m else None


def _sql(s: str) -> str:
    return s.replace("'", "''")


def county_address_url(number: str, street: str) -> str:
    where = (f"SitusCity='PIEDMONT' AND SitusStreetNumber='{_sql(number)}' "
             f"AND SitusStreetName='{_sql(street)}'")
    q = urllib.parse.urlencode({"where": where, "outFields": COUNTY_FIELDS, "returnGeometry": "true",
                                "outSR": FEET_SR, "f": "json"})
    return f"{COUNTY['url']}/query?{q}"


def county_near_url(lat: float, lon: float) -> str:
    q = urllib.parse.urlencode({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                "distance": COUNTY_RADIUS_M, "units": "esriSRUnit_Meter",
                                "spatialRel": "esriSpatialRelIntersects", "outFields": COUNTY_FIELDS,
                                "returnGeometry": "true", "outSR": FEET_SR, "f": "json"})
    return f"{COUNTY['url']}/query?{q}"


def ring_area_sqft(geometry: dict | None) -> float | None:
    """Area of an ArcGIS polygon in square feet (rings are in FEET_SR). Holes subtract."""
    rings = (geometry or {}).get("rings") or []
    total = 0.0
    for r in rings:
        total += sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(r, r[1:])) / 2
    return abs(total) or None


def _county(number: str, street: str, lat, lon, fetch, today: str, notes: list[str]) -> dict:
    """Facts from the county layer for one address, or {} with a note saying why."""
    name = COUNTY["name"]
    feats = []
    try:
        feats = fetch(county_address_url(number, street)).get("features") or []
        if not feats and lat is not None and lon is not None:
            near = fetch(county_near_url(lat, lon)).get("features") or []
            feats = [f for f in near
                     if str(f["attributes"].get("SitusStreetNumber", "")).strip() == number
                     and " ".join(str(f["attributes"].get("SitusStreetName", "")).upper().split()) == street]
    except Exception as e:
        notes.append(f"{name}: unreachable ({type(e).__name__}).")
        return {}
    if not feats:
        notes.append(f"{name}: no parcel listed at {number} {street.title()}.")
        return {}
    src = name
    apns = sorted({(f["attributes"].get("PrintParcel") or f["attributes"].get("APN") or "").strip() for f in feats} - {""})
    if len(apns) > 1:
        notes.append(f"{name}: {len(apns)} parcels share this address, so lot size is not filled. "
                     "Check which one is yours.")
        return {"apn": {"value": ", ".join(apns), "source": src, "as_of": today}}
    facts = {}
    if apns:
        facts["apn"] = {"value": apns[0], "source": src, "as_of": today}
    sqft = ring_area_sqft(feats[0].get("geometry"))
    if sqft:
        facts["lot_size"] = {"value": f"{sqft:,.0f} sq ft", "source": f"{src} (area of the mapped parcel boundary)",
                             "as_of": today}
    return facts


def pick(attrs: dict) -> dict:
    """Map a raw attribute dict to our fields using CANDIDATES. Empty/zero values are skipped."""
    low = {k.lower(): v for k, v in attrs.items()}
    out = {}
    for ours, names in CANDIDATES.items():
        for n in names:
            v = low.get(n.lower())
            if v not in (None, "", 0, "0", " "):
                out[ours] = v
                break
    return out


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _point_providers(lat, lon, fetch, today: str, notes: list[str]) -> dict:
    for p in providers():
        try:
            data = fetch(query_url(p["url"], lat, lon))
        except Exception as e:
            notes.append(f"{p['name']}: unreachable ({type(e).__name__}).")
            continue
        feats = data.get("features") or []
        if not feats:
            notes.append(f"{p['name']}: no parcel at this point.")
            continue
        got = pick(feats[0].get("attributes", {}))
        facts, src = {}, p["name"]
        if "apn" in got:
            facts["apn"] = {"value": str(got["apn"]).strip(), "source": src, "as_of": today}
        sq, ac = _num(got.get("lot_sqft")), _num(got.get("acres"))
        if sq:
            facts["lot_size"] = {"value": f"{sq:,.0f} sq ft", "source": src, "as_of": today}
        elif ac:
            facts["lot_size"] = {"value": f"{ac * 43560:,.0f} sq ft ({ac:.3f} acres)", "source": src, "as_of": today}
        for k in ("year_built", "building_sqft", "bedrooms", "bathrooms"):
            if k in got:
                facts[k] = {"value": str(got[k]).strip(), "source": src, "as_of": today}
        if facts:
            return facts
        notes.append(f"{p['name']}: parcel found but no usable fields.")
    return {}


def lookup(lat, lon, fetch=None, today: str | None = None, address: str | None = None) -> tuple[dict, list[str]]:
    """Return ({field: {value, source, as_of}}, notes). `address` is the geocoder's matched address
    ('120 VISTA AVE, PIEDMONT, CA, 94611'). Never raises."""
    fetch = fetch or _get
    today = today or dt.date.today().isoformat()
    notes: list[str] = []
    parts = split_street(address or "")
    facts = _county(*parts, lat, lon, fetch, today, notes) if parts else {}
    if not parts:
        notes.append(f"{COUNTY['name']}: the address has no house number, so no parcel lookup was attempted.")
    if not facts and providers() and lat is not None and lon is not None:
        facts = _point_providers(lat, lon, fetch, today, notes)
    return facts, notes
