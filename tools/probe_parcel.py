#!/usr/bin/env python3
"""Probe candidate parcel services for an address, from a machine with network access.

  python tools/probe_parcel.py "21 Portsmouth Rd, Piedmont, CA"
  python tools/probe_parcel.py --latlon 37.82 -122.23
  python tools/probe_parcel.py "..." --url https://host/arcgis/rest/services/X/MapServer/0

Prints, per provider: whether it responds, its field names, the raw attributes of the parcel at
the point, and which of Plinth's fields would be filled. When one works, set
PLINTH_PARCEL_URL to its layer URL. Paste the output back if you want help mapping fields.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import parcel, property as prop  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address", nargs="?")
    ap.add_argument("--latlon", nargs=2, type=float)
    ap.add_argument("--url", action="append", default=[], help="extra layer URL to probe")
    a = ap.parse_args()
    if a.latlon:
        lat, lon = a.latlon
    elif a.address:
        g = prop.geocode(a.address)
        if not g:
            sys.exit("Geocoder returned no match (or is unreachable).")
        lon, lat = g["coordinates"]["x"], g["coordinates"]["y"]
        print(f"Geocoded: {g['matchedAddress']}  lat={lat} lon={lon}\n")
    else:
        ap.error("give an address or --latlon")
    layers = [{"name": f"extra {u}", "url": u} for u in a.url] + parcel.providers()
    for p in layers:
        print("=" * 70, f"\n{p['name']}\n{p['url']}")
        try:
            meta = parcel._get(p["url"] + "?f=json")
            print("fields:", ", ".join(f["name"] for f in meta.get("fields", [])) or "(none listed)")
        except Exception as e:
            print("metadata failed:", repr(e))
        try:
            data = parcel._get(parcel.query_url(p["url"], lat, lon))
        except Exception as e:
            print("query failed:", repr(e))
            continue
        feats = data.get("features") or []
        if not feats:
            print("no parcel returned", json.dumps(data)[:300])
            continue
        attrs = feats[0].get("attributes", {})
        print("attributes:", json.dumps(attrs, indent=2, default=str))
        print("Plinth would fill:", parcel.pick(attrs))


if __name__ == "__main__":
    main()
