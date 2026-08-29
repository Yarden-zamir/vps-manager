"""Turn harvested photos into wall directions, under explicit rules.

Most photos taken near a crag do not point at the crag. A heading that is wrong is
worse than no heading, because the model reports it with the same confidence either
way, so every rule here throws work away rather than guessing.

  R1 proximity   the camera stood within RADIUS_M of the sector
  R2 heading     the EXIF carries a camera direction; magnetic ones take the local
                 declination
  R3 looking up  along that heading the ground rises at least MIN_RISE_DEG within
                 the near field. Sky, valley floor and portraits fail this
  R4 square on   that rise is close to the steepest in a window around the heading,
                 so the camera points into the wall and not along it
  R5 consensus   the surviving headings agree; their circular spread is reported and
                 a wide one is not trusted

The thresholds are swept rather than chosen, because a rule that only ever passes
everything or nothing is not a filter. Scored the same way as everything else:
against Sun Beta's curves for the sector.

Result on the Commons harvest: it does not work. See the README. The mechanism is
sound and the sourcing is not, so this script is kept as the measurement that shows
which of the two failed.

    uv run python scripts/aspect_from_photos.py out/commons.json
"""
import json
import sys
from datetime import date

import numpy as np

from shademodel import terrain as T
from shademodel import validate as V
from shademodel.dem import fetch_copernicus, to_utm
from shademodel.israel import TZ, matched_sectors
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, build_wall, normal_from

RADIUS_M = 250.0  # R1
DECLINATION_DEG = 4.6  # R2, east positive, Israel
MIN_RISE_DEG = 5.0  # R3
LOOK_NEAR_M, LOOK_FAR_M = 20.0, 400.0  # R3 near field
SQUARE_WINDOW_DEG = 40.0  # R4
SQUARE_TOLERANCE_DEG = 3.0  # R4
EYE_HEIGHT_M = 1.6

CFG = WallConfig()
TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
FIT = {(r["area"], r["sector"]): r["aspect_fit"] for r in json.load(open("out/israel_fit.json"))}
AUTO = {(r["area"], r["sector"]): r["aspect"] for r in json.load(open("out/report.json"))["auto"]}


def true_heading(photo: dict) -> float:
    """R2. A magnetic heading needs the declination; a true one is already true."""
    bump = DECLINATION_DEG if photo["heading_ref"] == "M" else 0.0
    return (photo["heading"] + bump) % 360.0


def looks_at_rock(patch, lat: float, lon: float, heading: float) -> tuple[float, float]:
    """Ray-march from where the camera stood: how high the ground rises along the
    heading, and how high it rises at the best heading nearby."""
    _, cx, cy = to_utm(lat, lon)
    r, c = patch.rowcol(cx, cy)
    if not (0 <= r < patch.z.shape[0] and 0 <= c < patch.z.shape[1]):
        return -90.0, 0.0
    eye = float(patch.z[r, c]) + EYE_HEIGHT_M
    azimuths = np.arange(0, 360, 1.0)
    profile = T.horizon(patch, np.array([cx]), np.array([cy]), np.array([eye]),
                        azimuths, LOOK_NEAR_M, LOOK_FAR_M, ratio=1.05)[0]
    i = int(round(heading)) % 360
    rise = float(profile[i])
    window = np.arange(i - int(SQUARE_WINDOW_DEG), i + int(SQUARE_WINDOW_DEG) + 1) % 360
    return rise, float(profile[window].max())


def circular_mean(angles: np.ndarray) -> float:
    a = np.radians(angles)
    return float(np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) % 360.0)


def circular_spread(angles: np.ndarray, centre: float) -> float:
    if angles.size < 2:
        return 0.0
    return float(np.ptp((angles - centre + 180) % 360 - 180))


def score(lat: float, lon: float, aspect: float, area: str, sector: str) -> float:
    wall = build_wall(sector, lat, lon, TZ, CFG, aspect_deg=0.0)
    out = []
    for d in DAYS:
        track = sun_track(lat, lon, d, TZ, altitude=float(wall.z.mean()))
        n = normal_from(aspect, CFG.dip_deg)
        lit = (((n @ track.unit_vectors().T) > 0)[None, :]
               & (track.elevation[None, :] > wall.horizon_at(track.azimuth))
               & (track.elevation[None, :] > 0))
        out.append(V.compare(TRUTH, area, sector, d, track.hours, 1.0 - lit.mean(axis=0))["mae"])
    return float(np.mean(out))


def candidates(photos, radius_m):
    """Every sector paired with the photos taken inside its radius, R1 applied."""
    out = []
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        for sector, (lat, lon) in sectors.items():
            _, sx, sy = to_utm(lat, lon)
            near = []
            for p in photos:
                _, px, py = to_utm(p["lat"], p["lon"])
                d = float(np.hypot(px - sx, py - sy))
                if d <= radius_m:
                    near.append((p, d))
            if near:
                out.append((area, sector, lat, lon, near))
    return out


def measure(photos, radius_m, min_rise_deg, square_tolerance_deg, verbose=False):
    rows, funnel = [], {"R1": 0, "R3": 0, "R4": 0}
    for area, sector, lat, lon, near in candidates(photos, radius_m):
        patch = fetch_copernicus(lat, lon, CFG.patch_half_m, CFG.pixel_m, snap_m=300.0)
        funnel["R1"] += len(near)
        kept = []
        for p, d in near:
            h = true_heading(p)
            rise, peak = looks_at_rock(patch, p["lat"], p["lon"], h)
            if rise >= min_rise_deg:
                funnel["R3"] += 1
                if rise >= peak - square_tolerance_deg:
                    funnel["R4"] += 1
                    kept.append((h, d, p, rise))
        if not kept:
            continue
        headings = np.array([k[0] for k in kept])
        facing = circular_mean((headings + 180.0) % 360.0)
        spread = circular_spread((headings + 180.0) % 360.0, facing)
        fitted = FIT[(area, sector)]
        rows.append(dict(area=area, sector=sector, n=len(kept), facing=facing, spread=spread,
                         fitted=fitted, error=abs((facing - fitted + 180) % 360 - 180),
                         mae_photo=score(lat, lon, facing, area, sector),
                         mae_auto=score(lat, lon, AUTO[(area, sector)], area, sector),
                         mae_fitted=score(lat, lon, fitted, area, sector),
                         photos=[k[2]["title"] for k in kept]))
        if verbose:
            print(f"{area:12s} {sector:24s} {len(near):2d} near -> {len(kept):2d} kept  "
                  f"wall faces {facing:3.0f} (spread {spread:3.0f})  fitted {fitted:3.0f}  "
                  f"err {rows[-1]['error']:3.0f} deg")
    return rows, funnel


def main(path: str) -> int:
    photos = json.loads(open(path).read())
    print(f"{len(photos)} harvested photos carry a camera heading")
    print(f"{sum(len(n) for *_, n in candidates(photos, RADIUS_M))} photo-sector pairs "
          f"within {RADIUS_M:.0f} m\n")

    print(f"{'radius':>7} {'min rise':>9} {'square tol':>11} {'kept':>5} {'sectors':>8} "
          f"{'dir err':>8} {'MAE photo':>10} {'MAE derived':>12} {'MAE fitted':>11}")
    best = None
    for radius in (150.0, 250.0, 400.0):
        for min_rise in (2.0, 5.0):
            for tol in (3.0, 10.0, 25.0, 90.0):
                rows, funnel = measure(photos, radius, min_rise, tol)
                if not rows:
                    print(f"{radius:7.0f} {min_rise:9.0f} {tol:11.0f} {funnel['R4']:5d} {0:8d}")
                    continue
                line = (f"{radius:7.0f} {min_rise:9.0f} {tol:11.0f} {funnel['R4']:5d} {len(rows):8d} "
                        f"{np.mean([r['error'] for r in rows]):6.0f} deg "
                        f"{np.mean([r['mae_photo'] for r in rows]):10.3f} "
                        f"{np.mean([r['mae_auto'] for r in rows]):12.3f} "
                        f"{np.mean([r['mae_fitted'] for r in rows]):11.3f}")
                print(line, flush=True)
                key = np.mean([r["mae_photo"] for r in rows])
                if best is None or key < best[0]:
                    best = (key, radius, min_rise, tol, rows)
    if best is None:
        print("\nno combination of thresholds produced a usable photo")
        return 0
    print(f"\nbest: radius {best[1]:.0f} m, min rise {best[2]:.0f} deg, square tolerance {best[3]:.0f} deg")
    rows, _ = measure(photos, best[1], best[2], best[3], verbose=True)
    json.dump(rows, open("out/photo_aspect.json", "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "out/commons.json"))
