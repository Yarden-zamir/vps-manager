"""Pull Sun Beta's published shade curves for one country, as a reference set.

Their pages are server rendered and carry the whole year in a JSON island, so one
request per crag is enough. Output is a reference set for scoring this model. It
is their data: keep it local, do not redistribute.

    uv run python scripts/scrape_sunbeta.py israel data/sunbeta_truth.json
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from lxml import html as LH

BASE = "https://sunbeta.app"


def state(client: httpx.Client, path: str) -> dict | None:
    r = client.get(f"{BASE}/{path}")
    r.raise_for_status()
    islands = LH.fromstring(r.content).xpath('//script[@id="ng-state"]')
    return json.loads(islands[0].text) if islands else None


def main(country: str, out_path: str) -> int:
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        listing = LH.fromstring(c.get(f"{BASE}/{quote(country.title())}").content)
        areas = sorted({h for h in listing.xpath("//a/@href") if h.startswith(f"/{country.lower()}/")})
        out = {}
        for href in areas:
            data = state(c, href.lstrip("/").replace(" ", "%20"))
            shade = (data or {}).get("shade_data")
            if not shade or "sectors" not in shade:
                print(f"  {href}: no data")
                continue
            out[shade["name"]] = shade["sectors"]
            print(f"  {shade['name']}: {len(shade['sectors'])} sectors")
            time.sleep(1.0)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out))
    print(f"{len(out)} crags -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
