"""What grounds the model: a plain state log, or a transition?

A coordinate fixes everything the model needs except one number, the direction the
wall faces. So one observation is in principle enough to close it. This measures how
much a single observation actually closes, for the two kinds someone can record:

  state       "at 14:00 on this date it was in the shade"
  transition  "it came into the sun at about 12:15 on this date"

A state rules out every direction that predicts the opposite. It is a half answer:
cheap to log, weak on its own. A transition pins the direction to a narrow band,
because the sun sweeps past the wall's edge-on angle only twice a day.
"""
import json
from datetime import date

import numpy as np

from shademodel import validate as V
from shademodel.israel import TZ, all_sector_positions, matched_sectors
from shademodel.observe import terrain_aspect
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, build_wall, normal_from

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
CANDIDATES = np.arange(0, 360, 2.0)
CFG = WallConfig()
CLIMBING_HOURS = (8.0, 17.0)  # when someone is actually at the crag to log anything
SEEDS = 24


def shade_cube(wall):
    """Shade for every candidate direction, on every date, at every quarter hour."""
    cube, grids = {}, {}
    for d in DAYS:
        track = sun_track(wall.lat, wall.lon, d, wall.tz, altitude=float(wall.z.mean()))
        above = track.elevation[None, :] > wall.horizon_at(track.azimuth)  # (level, time)
        up = track.elevation > 0
        normals = np.array([normal_from(a, CFG.dip_deg) for a in CANDIDATES])
        facing = (normals @ track.unit_vectors().T) > 0  # (candidate, time)
        lit = facing[:, None, :] & above[None, :, :] & up[None, None, :]
        cube[d] = 1.0 - lit.mean(axis=1)  # (candidate, time)
        grids[d] = track.hours
    return cube, grids


def pick(good: np.ndarray, prior: float) -> float:
    if good.size == 0:
        return prior
    return float(good[np.argmin(np.abs((good - prior + 180) % 360 - 180))])


def fit_states(cube, grids, truth_state, rng, k: int, prior: float) -> float:
    """Fit from k logged states: date, time, and whether it was sunny or shady."""
    votes = np.zeros(CANDIDATES.size)
    for _ in range(k):
        d = DAYS[rng.integers(len(DAYS))]
        hours = grids[d]
        usable = np.flatnonzero((hours >= CLIMBING_HOURS[0]) & (hours <= CLIMBING_HOURS[1]))
        i = usable[rng.integers(usable.size)]
        observed = truth_state[d][i]
        votes += np.abs((cube[d][:, i] > 0.5).astype(float) - observed)
    return pick(CANDIDATES[votes <= votes.min() + 1e-9], prior)


def fit_transition(cube, grids, area, sector, day, prior: float) -> float:
    th, tv = V.truth_curve(TRUTH, area, sector, day)
    grid = np.arange(th[0], th[-1] + 1e-9, 0.25)
    marks = V.signed_crossings(grid, V.on_grid(th, tv, grid))
    if not marks:
        return prior
    t_obs, way = marks[0]
    miss = []
    for row in cube[day]:
        got = [t for t, w in V.signed_crossings(grids[day], row) if w == way]
        miss.append(min((abs(t - t_obs) for t in got), default=6.0))
    miss = np.array(miss)
    return pick(CANDIDATES[miss <= max(miss.min() + 1e-9, 0.25)], prior)


def score(cube, grids, area, sector, aspect: float) -> float:
    i = int(np.argmin(np.abs(CANDIDATES - aspect)))
    return float(np.mean([V.compare(TRUTH, area, sector, d, grids[d], cube[d][i])["mae"] for d in DAYS]))


def main() -> int:
    counts = [1, 2, 4, 8, 16, 32]
    totals = {("state", k): [] for k in counts}
    totals[("transition", 1)] = []
    totals[("none", 0)] = []
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        for name, (lat, lon) in sectors.items():
            wall = build_wall(name, lat, lon, TZ, CFG, aspect_deg=0.0)
            cube, grids = shade_cube(wall)
            prior = terrain_aspect(lat, lon, CFG)
            truth_state = {}
            for d in DAYS:
                th, tv = V.truth_curve(TRUTH, area, sector=name, day=d)
                truth_state[d] = (V.on_grid(th, tv, grids[d]) > 0.5).astype(float)
            totals[("none", 0)].append(score(cube, grids, area, name, prior))
            totals[("transition", 1)].append(score(cube, grids, area, name,
                                                   fit_transition(cube, grids, area, name, date(2026, 7, 21), prior)))
            for k in counts:
                runs = [score(cube, grids, area, name,
                              fit_states(cube, grids, truth_state, np.random.default_rng(s), k, prior))
                        for s in range(SEEDS)]
                totals[("state", k)].append(float(np.mean(runs)))
            print(f"{area:12s} {name:26s} done", flush=True)

    print(f"\n{len(totals[('none', 0)])} sectors, {SEEDS} random draws per sector\n")
    print(f"{'what you logged':>34} {'MAE':>7}")
    print(f"{'nothing':>34} {np.mean(totals[('none', 0)]):7.3f}")
    for k in counts:
        label = f"{k} state{'s' if k > 1 else ''} (date, time, sun or shade)"
        print(f"{label:>34} {np.mean(totals[('state', k)]):7.3f}")
    print(f"{'1 transition (with direction)':>34} {np.mean(totals[('transition', 1)]):7.3f}")
    json.dump({f"{a}:{b}": v for (a, b), v in totals.items()}, open("out/state_fit.json", "w"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
