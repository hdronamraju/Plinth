"""Address type-ahead for the lookup box, via Photon (OpenStreetMap), restricted to Piedmont.

Called server-side so the browser never talks to a third party, results are cached, and failures
degrade to no suggestions. The chosen address is still resolved by the Census geocoder
(app/property.py), which stays the canonical record. Photon is a fair-use public service: keep the
debounce, cache and limits in place.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

PHOTON = "https://photon.komoot.io/api/"
BBOX = "-122.25,37.81,-122.215,37.835"  # lon_min,lat_min,lon_max,lat_max around Piedmont
UA = "Plinth/0.1 (Piedmont planning helper prototype)"
TTL = 600
MAX_CACHE = 500
_cache: dict[str, tuple[float, list[str]]] = {}


def _fetch(q: str, timeout: float = 4) -> dict:
    url = PHOTON + "?" + urllib.parse.urlencode({"q": q, "limit": 8, "lang": "en", "bbox": BBOX})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def format_results(data: dict, typed: str) -> list[str]:
    wants_number = any(ch.isdigit() for ch in typed)
    out, seen = [], set()
    for f in data.get("features", []):
        p = f.get("properties", {})
        street = p.get("street") or (p.get("name") if p.get("type") == "street" else None)
        num = p.get("housenumber")
        if not street or (wants_number and not num):
            continue
        city = p.get("city") or p.get("locality") or p.get("district") or ""
        if city and city.lower() != "piedmont":
            continue
        line = f"{num + ' ' if num else ''}{street}, Piedmont, CA" + (f" {p['postcode']}" if p.get("postcode") else "")
        if line.lower() not in seen:
            seen.add(line.lower())
            out.append(line)
        if len(out) == 6:
            break
    return out


def suggest(q: str, fetch=None) -> list[str]:
    """Up to 6 formatted Piedmont addresses for a partial query. Never raises."""
    q = " ".join((q or "").split())
    if len(q) < 3 or len(q) > 100:
        return []
    key = q.lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        res = format_results((fetch or _fetch)(q if "piedmont" in key else q + " Piedmont"), q)
    except Exception:
        return []  # not cached, so a transient failure can recover
    if len(_cache) >= MAX_CACHE:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.time(), res)
    return res
