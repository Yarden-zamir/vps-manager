"""Cliff lines from OpenStreetMap.

A `natural=cliff` way runs along the top of the face with the lower ground on the
right of the way's direction, so a segment's bearing plus 90 degrees is the
direction the wall faces. Mappers do reverse ways by mistake, so the caller
should sanity check the side against the terrain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pyproj import Transformer

from .dem import CACHE, grid_convergence_deg, utm_crs


@dataclass(frozen=True)
class CliffHit:
    aspect_deg: float
    distance_m: float
    way_id: str


def fetch_cliffs(lat: float, lon: float, pad_deg: float = 0.012) -> list[tuple[str, list[tuple[float, float]]]]:
    """Cliff ways around a point, straight from the OSM map call. Cached on disk."""
    import httpx
    from lxml import etree

    box = (round(lon - pad_deg, 4), round(lat - pad_deg, 4), round(lon + pad_deg, 4), round(lat + pad_deg, 4))
    path = CACHE / f"osm_{box[0]}_{box[1]}_{box[2]}_{box[3]}.json"
    if path.exists():
        return [(w, [tuple(p) for p in pts]) for w, pts in json.loads(path.read_text())]

    url = "https://api.openstreetmap.org/api/0.6/map"
    r = httpx.get(url, params={"bbox": ",".join(str(b) for b in box)}, timeout=180)
    r.raise_for_status()
    doc = etree.fromstring(r.content)
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon"))) for n in doc.iter("node")}
    ways = []
    for w in doc.iter("way"):
        if not any(t.get("k") == "natural" and t.get("v") == "cliff" for t in w.findall("tag")):
            continue
        pts = [nodes[nd.get("ref")] for nd in w.findall("nd") if nd.get("ref") in nodes]
        if len(pts) >= 2:
            ways.append((w.get("id"), pts))
    path.write_text(json.dumps(ways))
    return ways


def nearest_cliff(
    lat: float, lon: float, max_distance_m: float = 60.0, window_m: float = 40.0
) -> CliffHit | None:
    """Facing direction of the cliff closest to a point.

    The direction comes from the stretch of the way within `window_m` of the
    closest point, not from one segment. Mapped vertices are metres apart and a
    single segment's bearing swings by tens of degrees between them.
    """
    ways = fetch_cliffs(lat, lon)
    if not ways:
        return None
    crs = utm_crs(lat, lon)
    convergence = grid_convergence_deg(crs, lat, lon)
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    sx, sy = tf.transform(lon, lat)
    best: CliffHit | None = None
    for way_id, pts in ways:
        xs, ys = tf.transform([q[1] for q in pts], [q[0] for q in pts])
        p = np.column_stack([xs, ys])
        a, v = p[:-1], p[1:] - p[:-1]
        length2 = (v**2).sum(axis=1)
        length2[length2 == 0] = np.inf
        t = np.clip(((sx - a[:, 0]) * v[:, 0] + (sy - a[:, 1]) * v[:, 1]) / length2, 0, 1)
        proj = a + t[:, None] * v
        d = np.hypot(sx - proj[:, 0], sy - proj[:, 1])
        i = int(np.argmin(d))
        if best is not None and d[i] >= best.distance_m:
            continue

        arc = np.concatenate([[0.0], np.cumsum(np.hypot(v[:, 0], v[:, 1]))])
        here = arc[i] + t[i] * np.hypot(*v[i])
        near = np.abs(arc - here) <= window_m
        if near.sum() >= 2:
            w = p[near]
            axis = np.linalg.eigh(np.cov((w - w.mean(axis=0)).T))[1][:, -1]
            if axis @ (p[-1] - p[0]) < 0:  # keep the way's own direction of travel
                axis = -axis
            bearing = float(np.degrees(np.arctan2(axis[0], axis[1])) % 360)
        else:
            bearing = float(np.degrees(np.arctan2(v[i, 0], v[i, 1])) % 360)
        best = CliffHit((bearing + 90 - convergence) % 360, float(d[i]), way_id)
    return best if best and best.distance_m <= max_distance_m else None
