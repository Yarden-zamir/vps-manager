"""What does ground resolution buy?

Red Rocks is the only Sun Beta area with public 1 m lidar. Averaging that one grid
down to coarser cells holds the terrain and the source fixed and changes only the
resolution, which is the question anyone deciding what elevation data to buy is
actually asking.

Two columns per resolution:
  derived   the wall direction taken from the grid, as a product would have to
  fitted    the direction that best reproduces Sun Beta, so only the horizon differs
"""
import json
from datetime import date

import numpy as np

from shademodel import terrain as T
from shademodel import validate as V
from shademodel.dem import fetch_3dep, to_utm
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, Wall, normal_from

TRUTH = V.load_truth("data/sunbeta_truth.json")
TZ = "America/Los_Angeles"
AREA = "Red Rocks"
SECTORS = {
    "Black Corridor": (36.1555975, -115.4361525),
    "Sweet Pain Wall": (36.15597, -115.43663),
    "The Gallery": (36.15672, -115.43841),
    "The Great Red Book Area": (36.15544, -115.43461),
    "Wall of Confusion": (36.15702, -115.43904),
}
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
FACTORS = [1, 2, 5, 10, 20, 30]
HALF_M = 500.0
CFG = WallConfig(height_m=25.0, dip_deg=90.0)


def wall_on(patch, lat, lon, aspect):
    """A wall at the sector, with its horizon read off this particular grid."""
    _, cx, cy = to_utm(lat, lon)
    r, c = patch.rowcol(cx, cy)
    z0 = float(patch.z[r, c])
    levels = (np.arange(CFG.n_levels) + 0.5) / CFG.n_levels * CFG.height_m
    z = z0 + levels
    azimuths = np.arange(0, 360, CFG.azimuth_step_deg)
    px = np.full(CFG.n_levels, cx)
    py = np.full(CFG.n_levels, cy)
    horizon = T.horizon(patch, px, py, z, azimuths, patch.pixel / 2, HALF_M * 0.9, ratio=1.05)
    n = np.tile(normal_from(aspect, CFG.dip_deg), (CFG.n_levels, 1))
    return Wall("s", lat, lon, TZ, aspect, z, n, horizon, azimuths, CFG)


def curve(wall, aspect, day):
    track = sun_track(wall.lat, wall.lon, day, wall.tz, altitude=float(wall.z.mean()))
    n = normal_from(aspect, CFG.dip_deg)
    lit = (((n @ track.unit_vectors().T) > 0)[None, :]
           & (track.elevation[None, :] > wall.horizon_at(track.azimuth))
           & (track.elevation[None, :] > 0))
    return track.hours, 1.0 - lit.mean(axis=0)


def score(wall, aspect, sector):
    return float(np.mean([V.compare(TRUTH, AREA, sector, d, *curve(wall, aspect, d))["mae"] for d in DAYS]))


def derived_aspect(patch, lat, lon, radius_m: float = 40.0, steep_fraction: float = 0.25):
    """Direction of the steepest ground around the sector, as that grid resolves it.

    Takes the area-weighted mean normal of the steepest cells inside a radius, rather
    than the gradient at one cell. On a fine grid that is the cliff face; on a coarse
    one it degrades to the hillside, which is the point of the comparison. The steep
    cells are chosen by rank, so no slope threshold has to be re-tuned per resolution.
    """
    _, cx, cy = to_utm(lat, lon)
    slope = T.slope_deg(patch)
    n = T.to_true_north(T.normals(patch), patch)
    gx, gy = patch.xy()
    near = (np.hypot(gx - cx, gy - cy) <= max(radius_m, patch.pixel * 1.5)) & np.isfinite(patch.z)
    if near.sum() < 3:
        return T.landform_aspect(patch, cx, cy, max(patch.pixel * 1.5, 2.0))
    cut = np.quantile(slope[near], 1.0 - steep_fraction)
    steep = near & (slope >= cut)
    weight = 1.0 / np.cos(np.radians(np.minimum(slope[steep], 85.0)))
    east = float(np.sum(n[steep][:, 0] * weight))
    north = float(np.sum(n[steep][:, 1] * weight))
    return float(np.degrees(np.arctan2(east, north)) % 360.0)


def main() -> int:
    rows = {f: {"derived_mae": [], "fitted_mae": [], "aspect_err": []} for f in FACTORS}
    for sector, (lat, lon) in SECTORS.items():
        fine = fetch_3dep(lat, lon, HALF_M, 1.0)
        best_wall = wall_on(fine, lat, lon, 0.0)
        fitted = min(np.arange(0, 360, 5.0), key=lambda a: score(best_wall, float(a), sector))
        for f in FACTORS:
            patch = fine.coarsen(f)
            wall = wall_on(patch, lat, lon, 0.0)
            got = derived_aspect(patch, lat, lon)
            rows[f]["derived_mae"].append(score(wall, got, sector))
            rows[f]["fitted_mae"].append(score(wall, float(fitted), sector))
            rows[f]["aspect_err"].append(abs((got - fitted + 180) % 360 - 180))
        print(f"{sector:26s} fitted direction {fitted:3.0f} deg", flush=True)

    print(f"\n{'resolution':>11} {'direction error':>16} {'MAE, derived':>13} {'MAE, fitted':>12}")
    for f in FACTORS:
        r = rows[f]
        print(f"{f:>8} m {np.mean(r['aspect_err']):13.0f} deg {np.mean(r['derived_mae']):13.3f} {np.mean(r['fitted_mae']):12.3f}")
    json.dump({str(f): {k: list(map(float, v)) for k, v in r.items()} for f, r in rows.items()},
              open("out/resolution_ladder.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
