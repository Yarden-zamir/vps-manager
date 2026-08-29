"""Ways to obtain the one number the coarse model cannot derive: where the wall faces.

Three, in rising order of effort and accuracy:

  terrain      the downhill direction of the landform. Free, wrong by about 50 deg.
  line         two points along the cliff, read off a satellite image or a map.
  observation  a remembered transition, "it went into the shade about quarter past
               twelve". Search the directions that reproduce it.

A single transition has two solutions, one either side of solar noon. Which way the
wall turned separates them, so always record that with the time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from . import validate as V
from .dem import fetch_copernicus, grid_convergence_deg, to_utm
from .sun import sun_track
from .terrain import landform_aspect
from .wall import WallConfig, Wall, build_wall, normal_from

MISS_PENALTY_H = 6.0  # cost of a direction that shows no matching transition at all


@dataclass(frozen=True)
class Observation:
    """What a climber standing at the sector can report."""

    day: date
    hour: float | None  # local decimal hour of the change; None for a whole day of one state
    into: str  # "sun" or "shade": the state it moved into, or held all day


@dataclass(frozen=True)
class AspectFit:
    degrees: float
    spread_deg: float  # width of the directions that fit as well; the uncertainty
    prior_deg: float


def terrain_aspect(lat: float, lon: float, cfg: WallConfig | None = None) -> float:
    """Downhill direction of the landform. The weakest source, and always available."""
    cfg = cfg or WallConfig()
    patch = fetch_copernicus(lat, lon, cfg.patch_half_m, cfg.pixel_m, snap_m=300.0)
    _, cx, cy = to_utm(lat, lon)
    return landform_aspect(patch, cx, cy, cfg.aspect_smooth_m)


def aspect_from_line(
    lat: float,
    lon: float,
    a: tuple[float, float],
    b: tuple[float, float],
    cfg: WallConfig | None = None,
    downhill_deg: float | None = None,
) -> float:
    """Wall direction from two points along the foot or the top of the cliff.

    The two points give the strike. The wall faces one of the perpendiculars; the
    terrain says which one is downhill. Pass `downhill_deg` to skip that lookup,
    for instance when the side is already known.
    """
    cfg = cfg or WallConfig()
    crs, ax, ay = to_utm(*a)
    _, bx, by = to_utm(*b)
    if np.hypot(bx - ax, by - ay) < 1.0:
        raise ValueError("the two points along the cliff are less than a metre apart")
    strike = np.degrees(np.arctan2(bx - ax, by - ay)) - grid_convergence_deg(crs, lat, lon)
    downhill = terrain_aspect(lat, lon, cfg) if downhill_deg is None else downhill_deg
    candidates = [(strike + 90) % 360, (strike - 90) % 360]
    return min(candidates, key=lambda c: abs((c - downhill + 180) % 360 - 180))


def _curve(wall: Wall, aspect: float, day: date, cfg: WallConfig):
    track = sun_track(wall.lat, wall.lon, day, wall.tz, altitude=float(wall.z.mean()))
    n = normal_from(aspect, cfg.dip_deg)
    lit = (
        ((n @ track.unit_vectors().T) > 0)[None, :]
        & (track.elevation[None, :] > wall.horizon_at(track.azimuth))
        & (track.elevation[None, :] > 0)
    )
    return track.hours, 1.0 - lit.mean(axis=0)


def aspect_from_observations(
    lat: float,
    lon: float,
    tz: str,
    observations: list[Observation],
    cfg: WallConfig | None = None,
    step_deg: float = 2.0,
    tolerance_h: float = 0.25,
) -> AspectFit:
    """Wall direction that reproduces what someone saw at the crag.

    Ties are broken towards the terrain direction, which is poor but never wrong by
    more than about ninety degrees. `spread_deg` reports how wide the surviving band
    is: a wide band means one more observation, in another season, would pay.
    """
    cfg = cfg or WallConfig()
    if not observations:
        raise ValueError("no observations given")
    wall = build_wall("fit", lat, lon, tz, cfg, aspect_deg=0.0)
    prior = terrain_aspect(lat, lon, cfg)
    candidates = np.arange(0, 360, step_deg)

    errors = []
    for aspect in candidates:
        miss = []
        for obs in observations:
            hours, shade = _curve(wall, float(aspect), obs.day, cfg)
            if obs.hour is None:
                lit = shade[hours >= 8.0] < 0.5
                held = lit.mean() if obs.into == "sun" else 1.0 - lit.mean()
                miss.append(MISS_PENALTY_H * (1.0 - held))
            else:
                marks = [t for t, way in V.signed_crossings(hours, shade) if way == obs.into]
                miss.append(min((abs(t - obs.hour) for t in marks), default=MISS_PENALTY_H))
        errors.append(float(np.mean(miss)))
    errors = np.array(errors)

    good = candidates[errors <= max(errors.min() + 1e-9, tolerance_h)]
    offset = np.abs((good - prior + 180) % 360 - 180)
    best = float(good[np.argmin(offset)])
    near = good[np.abs((good - best + 180) % 360 - 180) <= 90]
    spread = float(np.ptp((near - best + 180) % 360 - 180)) if near.size > 1 else 0.0
    return AspectFit(best, spread, prior)


def parse_observation(text: str) -> Observation:
    """Parse `2026-06-21:shade@12:15`, or `2026-12-21:shade` for a whole day."""
    day_text, _, rest = text.partition(":")
    into, _, hhmm = rest.partition("@")
    if into not in ("sun", "shade"):
        raise ValueError(f"{text!r}: expected 'sun' or 'shade', got {into!r}")
    hour = None
    if hhmm:
        h, _, m = hhmm.partition(":")
        hour = int(h) + int(m or 0) / 60.0
    return Observation(date.fromisoformat(day_text), hour, into)
