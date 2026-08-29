"""Harvest camera headings for Israeli sectors from Wikimedia Commons.

Commons publishes the EXIF of every file through its API, including the camera's
compass heading, and lets you search by position. That makes it a systematic,
open source of exactly the number the coarse elevation model cannot supply.

Most photos near a crag do not point at the crag, so the rules below decide which
ones count. They are deliberately conservative: a wrong heading is worse than no
heading, because the model reports it with the same confidence either way.

    uv run python scripts/harvest_commons.py out/commons.json
"""
import json
import sys
import time
from pathlib import Path

import httpx

from shademodel.israel import all_sector_positions, matched_sectors

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "shade-model research (https://github.com/Yarden-zamir; dev@yarden-zamir.com)"}
SEARCH_RADIUS_M = 500  # the API caps this at 10 km; a crag is a small thing
PAUSE_S = 1.5


def _rational(text: str) -> float | None:
    """Commons hands EXIF rationals back as strings like '42/1' or plain numbers."""
    try:
        if "/" in str(text):
            a, b = str(text).split("/")
            return float(a) / float(b) if float(b) else None
        return float(text)
    except (TypeError, ValueError):
        return None


def _dms(value) -> float | None:
    """A GPS coordinate, which Commons may give as a number or as three rationals."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return _rational(value)
    if isinstance(value, list) and len(value) == 3:
        parts = [_rational(v) for v in value]
        return None if None in parts else parts[0] + parts[1] / 60 + parts[2] / 3600
    return None


def fetch(client: httpx.Client, lat: float, lon: float) -> list[dict]:
    params = {
        "action": "query", "format": "json", "generator": "geosearch",
        "ggscoord": f"{lat}|{lon}", "ggsradius": SEARCH_RADIUS_M, "ggslimit": 100, "ggsnamespace": 6,
        "prop": "imageinfo", "iiprop": "url|commonmetadata|extmetadata",
    }
    for attempt in range(5):
        r = client.get(API, params=params)
        if r.status_code == 200:
            break
        time.sleep(4 * (attempt + 1))
    else:
        return []
    pages = (r.json().get("query") or {}).get("pages", {})
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = {m["name"]: m["value"] for m in info.get("commonmetadata", [])}
        heading = _rational(meta.get("GPSImgDirection"))
        if heading is None:
            continue
        clat, clon = _dms(meta.get("GPSLatitude")), _dms(meta.get("GPSLongitude"))
        if clat is None or clon is None:
            continue
        if str(meta.get("GPSLatitudeRef", "N")).upper().startswith("S"):
            clat = -clat
        if str(meta.get("GPSLongitudeRef", "E")).upper().startswith("W"):
            clon = -clon
        out.append({
            "title": page["title"],
            "url": info.get("descriptionurl"),
            "lat": clat, "lon": clon,
            "heading": heading % 360.0,
            "heading_ref": str(meta.get("GPSImgDirectionRef", ""))[:1].upper(),
            "taken": meta.get("DateTimeOriginal"),
        })
    return out


def main(out_path: str) -> int:
    seen: dict[str, dict] = {}
    targets = {}
    for area, sectors in matched_sectors("data/sunbeta_truth.json", "data/il_coords.json").items():
        for name, pos in sectors.items():
            targets[(area, name)] = pos
        for name, pos in all_sector_positions("data/il_coords.json", area).items():
            targets.setdefault((area, f"~{name}"), pos)

    with httpx.Client(headers=UA, timeout=120, follow_redirects=True) as client:
        for (area, name), (lat, lon) in targets.items():
            hits = fetch(client, lat, lon)
            for h in hits:
                seen.setdefault(h["title"], h)
            print(f"{area:12s} {name:28s} {len(hits):3d} photo(s) with a heading", flush=True)
            time.sleep(PAUSE_S)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(list(seen.values()), indent=1))
    print(f"\n{len(seen)} distinct photos carrying a camera heading -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "out/commons.json"))
