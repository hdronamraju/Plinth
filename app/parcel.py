"""Parcel lookup from public ArcGIS layers, by geocoded point.

Providers are tried in order; the first that returns a parcel wins. Only fields the service
actually returns are used. Nothing is inferred. Every value is labeled with the provider name
and date. Candidate layers are UNVERIFIED: run tools/probe_parcel.py on a machine with network
access to see which one works, then set PLINTH_PARCEL_URL to it (it is tried first).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request

PROVIDERS = [
    {"name": "California statewide parcels (UCD_Parcels)",
     "url": "https://services.gis.ca.gov/arcgis/rest/services/Boundaries/UCD_Parcels/MapServer/0"},
    {"name": "Alameda County roll layer (mobile.alamedaca.gov layer 34)",
     "url": "https://mobile.alamedaca.gov/arcgis/rest/services/LucityEdit/MapServer/34"},
]

# our field -> candidate attribute names (case-insensitive), first match wins
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
    custom = os.environ.get("PLINTH_PARCEL_URL")
    return ([{"name": "Configured parcel service (PLINTH_PARCEL_URL)", "url": custom}] if custom else []) + PROVIDERS


def _get(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def query_url(layer_url: str, lat: float, lon: float) -> str:
    q = urllib.parse.urlencode({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
                                "returnGeometry": "false", "f": "json"})
    return f"{layer_url.rstrip('/')}/query?{q}"


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


def lookup(lat, lon, fetch=None, today: str | None = None) -> tuple[dict, list[str]]:
    """Return ({field: {value, source, as_of}}, notes). Never raises."""
    fetch = fetch or _get
    today = today or dt.date.today().isoformat()
    notes: list[str] = []
    if lat is None or lon is None:
        return {}, ["No coordinates, so no parcel lookup was attempted."]
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
        facts = {}
        src = f"{p['name']}"
        if "apn" in got:
            facts["apn"] = {"value": str(got["apn"]).strip(), "source": src, "as_of": today}
        sq = _num(got.get("lot_sqft"))
        ac = _num(got.get("acres"))
        if sq:
            facts["lot_size"] = {"value": f"{sq:,.0f} sq ft", "source": src, "as_of": today}
        elif ac:
            facts["lot_size"] = {"value": f"{ac * 43560:,.0f} sq ft ({ac:.3f} acres)", "source": src,
                                 "as_of": today}
        for k in ("year_built", "building_sqft", "bedrooms", "bathrooms"):
            if k in got:
                facts[k] = {"value": str(got[k]).strip(), "source": src, "as_of": today}
        if facts:
            return facts, notes
        notes.append(f"{p['name']}: parcel found but no usable fields.")
    return {}, notes
