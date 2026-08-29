"""Israeli crags: pair Sun Beta's published curves with 27crags sector positions."""

from __future__ import annotations

import json
import re
from pathlib import Path

TZ = "Asia/Jerusalem"

# Sun Beta and 27crags name the same wall differently in a handful of places.
ALIASES = {
    ("Gita East", "Stage"): "The Stage",
    ("Gita East", "The Holy"): "Holy Cow",
    ("Gita East", "Walkabout"): "Walk About",
    ("Yonim", "Cave"): "The Cave",
    ("Beit Arye", "Cave"): "Cave sector",
    ("Beit Arye", "Shelf"): "The Shelf",
    ("Zanoah", "Boulder"): "The Boulder Sector",
    ("Zanoah", "King's Road"): "Royal Road",
    ("Timna", "Bara"): "Beera",
    ("Timna", "Ethica"): "Etica (ethics)",
    ("Timna", "First Steps"): "Tzeadim Rishonim (first steps)",
    ("Timna", "Metamorphosis"): "Metamorphosis Wall",
    ("Timna", "Safam Aliekum"): "Safam Aleh’kom",
    ("Timna", "Star Wars"): "Milchmet Hakochavim (star wars)",
    ("Timna", "Tablets of Stone"): "Luchot HaBrit (Tablets of Stone)",
    ("Timna", "The Bedouin Wall"): "Bedouin Wall",
    ("Timna", "The Cave (Leaning Boulder)"): "Leaning boulder (Cave)",
    ("Timna", "The Twins"): "HaTeomim (The Twins)",
    ("Timna", "Prisms"): "The Parisms",
    ("Timna", "Selfi Boulder"): "Selfie",
}


def _norm(name: str) -> str:
    s = name.lower().replace("’", "'")
    s = re.sub(r"\b(the|sector|wall|area)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def matched_sectors(truth_path: str | Path, coords_path: str | Path) -> dict[str, dict[str, tuple[float, float]]]:
    """Sun Beta sector -> position, for every sector both sources agree on."""
    truth = json.loads(Path(truth_path).read_text())
    coords = json.loads(Path(coords_path).read_text())
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for area, entry in coords.items():
        if area not in truth:
            continue
        by_norm = {_norm(k): k for k in entry["sectors"]}
        pairs = {}
        for sb_name in truth[area]:
            key = ALIASES.get((area, sb_name), sb_name)
            hit = entry["sectors"].get(key) or entry["sectors"].get(by_norm.get(_norm(key), ""))
            if hit:
                pairs[sb_name] = tuple(hit)
        if pairs:
            out[area] = pairs
    return out


def all_sector_positions(coords_path: str | Path, area: str) -> dict[str, tuple[float, float]]:
    """Every 27crags sector of a crag, matched or not. Neighbours define the strike."""
    coords = json.loads(Path(coords_path).read_text())
    return {k: tuple(v) for k, v in coords[area]["sectors"].items() if v}
