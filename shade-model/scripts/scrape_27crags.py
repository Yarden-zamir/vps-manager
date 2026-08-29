"""Pull sector positions for the Israeli crags from 27crags.

Sector coordinates are the one input the model cannot derive. 27crags carries
them for most Israeli crags and names sectors the same way Sun Beta does.

    uv run python scripts/scrape_27crags.py data/il_coords.json
"""
import json
import re
import sys
import time
from pathlib import Path

import httpx
from lxml import html as LH

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36"}
LATLNG = re.compile(r'lat[=":\s]+(-?\d{1,2}\.\d{4,}).{0,40}?lng[=":\s]+(-?\d{1,3}\.\d{4,})', re.S)

SLUGS = {
    "Beit Arye": "beit-arye",
    "Dalton": "dalton",
    "Ein Fara": "ein-fara",
    "Gita East": "gita",
    "Shilat": "shilat",
    "Timna": "timna",
    "Vanishing (Hane'elam)": "vanishing-cliff",
    "Yonim": "yonim",
    "Zanoah": "zanoah",
    "Zikhron": "zihron",
}


def coords(text: str) -> tuple[float, float] | None:
    m = LATLNG.search(text)
    return (float(m.group(1)), float(m.group(2))) if m else None


def main(out_path: str) -> int:
    out = {}
    with httpx.Client(headers=UA, timeout=90, follow_redirects=True) as c:
        for name, slug in SLUGS.items():
            page = c.get(f"https://27crags.com/crags/{slug}/routelist")
            doc = LH.fromstring(page.text)
            sectors = {}
            for el in doc.xpath('//*[contains(@class,"sector-item")]'):
                title, href = el.get("title"), el.get("href")
                if not title or not href or href.endswith("/routelist"):
                    continue
                sectors[title] = coords(c.get("https://27crags.com" + href).text)
                time.sleep(0.3)
            out[name] = {"slug": slug, "crag": coords(page.text), "sectors": sectors}
            print(f"{name}: {len(sectors)} sectors")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
