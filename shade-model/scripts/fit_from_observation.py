"""How much is one field observation worth?

A climber cannot read a wall's compass bearing off a map, but can say "it went
into the shade at about quarter past twelve". This measures how well a single
remembered transition pins the wall direction, and how much a second one adds.

The search is seeded with the automatic estimate, so the observation only has to
resolve which of the candidate directions is right, not find it from nothing.
"""
import json
import sys
from datetime import date

import numpy as np

from shademodel import validate as V
from shademodel.aspect import crag_aspects
from shademodel.israel import TZ, all_sector_positions, matched_sectors
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, build_wall, normal_from

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
CANDIDATES = np.arange(0, 360, 5.0)
CFG = WallConfig()


def curve(wall, aspect: float, day: date):
    tr = sun_track(wall.lat, wall.lon, day, wall.tz, altitude=float(wall.z.mean()))
    n = normal_from(aspect, CFG.dip_deg)
    lit = ((n @ tr.unit_vectors().T) > 0)[None, :] & (tr.elevation[None, :] > wall.horizon_at(tr.azimuth)) & (tr.elevation[None, :] > 0)
    return tr.hours, 1.0 - lit.mean(axis=0)


def observations(area: str, sector: str, days: list[date]) -> list[tuple[date, float | None, str]]:
    """What a climber at the crag that day could report, taken from the reference set.

    Either a transition, as a time and the direction it went, or a whole day of
    one state. Both are things people actually remember.
    """
    out = []
    for d in days:
        th, tv = V.truth_curve(TRUTH, area, sector, d)
        grid = np.arange(th[0], th[-1] + 1e-9, 0.25)
        ref = V.on_grid(th, tv, grid)
        marks = V.signed_crossings(grid, ref)
        if marks:
            out += [(d, t, way) for t, way in marks]
        else:
            out.append((d, None, "shade" if ref.mean() > 0.5 else "sun"))
    return out


MISS_PENALTY_H = 6.0  # cost of a candidate that shows no matching transition at all


def fit(wall, obs, prior: float, tolerance_h: float = 0.25) -> float:
    """Direction that reproduces the observations, nearest the prior.

    A single transition time has two solutions, one either side of solar noon.
    Which way the wall turned separates them; the prior only breaks what is left.
    """
    errors = []
    for aspect in CANDIDATES:
        miss = []
        for d, t_obs, way in obs:
            hours, shade = curve(wall, aspect, d)
            marks = [t for t, w in V.signed_crossings(hours, shade) if w == way]
            if t_obs is None:  # a whole day of one state
                lit = shade[(hours >= 8.0)] < 0.5
                held = lit.mean() if way == "sun" else 1 - lit.mean()
                miss.append(MISS_PENALTY_H * (1.0 - held))
            else:
                miss.append(min((abs(t - t_obs) for t in marks), default=MISS_PENALTY_H))
        errors.append(float(np.mean(miss)))
    errors = np.array(errors)
    good = CANDIDATES[errors <= max(errors.min() + 1e-9, tolerance_h)]
    if good.size == 0:
        return prior
    offset = np.abs((good - prior + 180) % 360 - 180)
    return float(good[np.argmin(offset)])


def score(wall, aspect: float, area: str, sector: str) -> float:
    return float(np.mean([V.compare(TRUTH, area, sector, d, *curve(wall, aspect, d))["mae"] for d in DAYS]))


def main() -> int:
    rows = []
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        positions = all_sector_positions(COORDS_PATH, area)
        auto = {positions[k]: v for k, v in crag_aspects(positions, CFG).items()}
        for name, (lat, lon) in sectors.items():
            wall = build_wall(name, lat, lon, TZ, CFG, aspect_deg=0.0)
            prior = auto[(lat, lon)].degrees
            obs_summer = observations(area, name, [date(2026, 7, 21)])
            obs_both = obs_summer + observations(area, name, [date(2026, 1, 21)])
            row = dict(area=area, sector=name, prior=prior, mae_auto=score(wall, prior, area, name),
                       n_obs_summer=len(obs_summer), n_obs_both=len(obs_both))
            row["mae_1obs"] = score(wall, fit(wall, obs_summer, prior), area, name) if obs_summer else row["mae_auto"]
            row["mae_2obs"] = score(wall, fit(wall, obs_both, prior), area, name) if obs_both else row["mae_auto"]
            rows.append(row)
            print(f"{area:12s} {name:26s} obs {len(obs_summer)}/{len(obs_both)}  "
                  f"MAE auto {row['mae_auto']:.3f} -> 1 day {row['mae_1obs']:.3f} -> 2 days {row['mae_2obs']:.3f}", flush=True)
    json.dump(rows, open("out/observation_fit.json", "w"), indent=1)
    usable = [r for r in rows if r["n_obs_both"]]
    print(f"\n{len(rows)} sectors, {len(usable)} with a transition to observe")
    for key, label in [("mae_auto", "no observation"), ("mae_1obs", "one summer day"), ("mae_2obs", "summer and winter")]:
        print(f"  {label:20s} MAE {np.mean([r[key] for r in rows]):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
