"""Where a sector's wall faces, from whatever evidence exists for that crag.

A 30 m elevation model cannot see a 30 m cliff, so the facing direction has to
come from elsewhere. Three sources, best first:

  osm     a mapped `natural=cliff` line within a few tens of metres
  strike  the line that neighbouring sectors of the same crag trace
  terrain the downhill direction of the landform, which is only ever a fallback

The terrain direction is wrong by tens of degrees but never by more than ninety,
so it also settles which of the two sides of a line the wall faces.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dem import DemPatch, fetch_copernicus, to_utm
from .osmcliff import nearest_cliff
from .terrain import landform_aspect
from .wall import WallConfig


def strike_aspect(
    patch: DemPatch,
    x: float,
    y: float,
    neighbour_x: np.ndarray,
    neighbour_y: np.ndarray,
    downhill_deg: np.ndarray,
    radius_m: float = 250.0,
    min_neighbours: int = 2,
) -> float | None:
    """Wall azimuth from the line that neighbouring sectors of the same crag trace.

    Sectors are named points along a cliff, so their local trend is the cliff's
    strike and the wall faces one of the two perpendiculars. A coarse elevation
    model gets that angle wrong by tens of degrees but still knows which way is
    downhill, so the group's mean downhill direction picks between the two.
    `downhill_deg` holds the downhill direction of the point followed by each
    neighbour. Returns None when too few neighbours sit close enough.
    """
    d = np.hypot(neighbour_x - x, neighbour_y - y)
    near = np.flatnonzero((d > 0.5) & (d <= radius_m))
    if near.size < min_neighbours:
        return None
    w = 1.0 / (d[near] + 20.0)
    px = np.concatenate([[x], neighbour_x[near]])
    py = np.concatenate([[y], neighbour_y[near]])
    pw = np.concatenate([[w.sum()], w])
    mx, my = np.average(px, weights=pw), np.average(py, weights=pw)
    cov = np.cov(np.vstack([px - mx, py - my]), aweights=pw, bias=True)
    ex, ey = np.linalg.eigh(cov)[1][:, -1]  # strike direction, in grid coordinates

    group = np.radians(np.concatenate([downhill_deg[:1], downhill_deg[1:][near]]))
    ref = np.array([np.sin(group).mean(), np.cos(group).mean()])
    best, agree = None, -np.inf
    for sign in (1.0, -1.0):
        cand = patch.to_true(np.degrees(np.arctan2(sign * ey, -sign * ex)))
        a = np.radians(cand)
        dot = ref @ np.array([np.sin(a), np.cos(a)])
        if dot > agree:
            best, agree = float(cand), dot
    return best


@dataclass(frozen=True)
class AspectEstimate:
    degrees: float
    source: str
    detail: str = ""


# The terrain direction is itself wrong by up to about ninety degrees, so only a
# near opposite reading is evidence that a mapped cliff was drawn the wrong way.
FLIP_THRESHOLD_DEG = 135.0


def _flip_to(candidate: float, reference: float) -> float:
    """Keep a line's facing direction on the same side as the reference."""
    off = abs((candidate - reference + 180) % 360 - 180)
    return candidate if off <= FLIP_THRESHOLD_DEG else (candidate + 180) % 360


def _circular_mean(angles: list[float]) -> float:
    a = np.radians(angles)
    return float(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360)


def crag_aspects(
    sectors: dict[str, tuple[float, float]],
    cfg: WallConfig | None = None,
    fetch=fetch_copernicus,
    mode: str = "combined",  # "combined", "strike", "osm" or "terrain"
    osm_max_distance_m: float = 60.0,
    agree_deg: float = 45.0,
) -> dict[str, AspectEstimate]:
    """Facing direction for every sector of one crag. Solved together: the strike
    estimate needs the neighbours."""
    cfg = cfg or WallConfig()
    names = list(sectors)
    patches: dict[str, DemPatch] = {n: fetch(*sectors[n], cfg.patch_half_m, cfg.pixel_m, snap_m=300.0) for n in names}
    xy = {n: to_utm(*sectors[n])[1:] for n in names}
    terrain = {n: landform_aspect(patches[n], *xy[n], cfg.aspect_smooth_m) for n in names}
    px = np.array([xy[n][0] for n in names])
    py = np.array([xy[n][1] for n in names])
    dh = np.array([terrain[n] for n in names])

    out: dict[str, AspectEstimate] = {}
    for i, n in enumerate(names):
        osm = None
        if mode in ("combined", "osm"):
            hit = nearest_cliff(*sectors[n], max_distance_m=osm_max_distance_m)
            if hit is not None:
                osm = (_flip_to(hit.aspect_deg, terrain[n]), f"way {hit.way_id} at {hit.distance_m:.0f} m")

        strike = None
        if mode in ("combined", "strike"):
            keep = np.arange(len(names)) != i
            strike = strike_aspect(patches[n], px[i], py[i], px[keep], py[keep],
                                   np.concatenate([[dh[i]], dh[keep]]),
                                   radius_m=cfg.strike_radius_m, min_neighbours=cfg.min_neighbours)

        if osm and strike is not None:
            if abs((osm[0] - strike + 180) % 360 - 180) <= agree_deg:
                out[n] = AspectEstimate(_circular_mean([osm[0], strike]), "osm+strike", osm[1])
            else:
                out[n] = AspectEstimate(strike, "strike", f"osm disagreed ({osm[0]:.0f} deg, {osm[1]})")
        elif osm:
            out[n] = AspectEstimate(osm[0], "osm", osm[1])
        elif strike is not None:
            out[n] = AspectEstimate(strike, "strike")
        else:
            out[n] = AspectEstimate(terrain[n], "terrain")
    return out
