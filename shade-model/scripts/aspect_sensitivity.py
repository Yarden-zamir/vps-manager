"""How accurate does the wall direction have to be?

Perturbs the best-fitting direction of each sector and scores the result, so the
error budget of any method for obtaining that number can be read off directly.
"""
import json
from datetime import date

import numpy as np

from shademodel import validate as V
from shademodel.israel import TZ, matched_sectors
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, build_wall, normal_from

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
CFG = WallConfig()
FIT = {(r["area"], r["sector"]): r["aspect_fit"] for r in json.load(open("out/israel_fit.json"))}


def score(wall, aspect, area, sector):
    mae, arrive, leave = [], [], []
    for d in DAYS:
        tr = sun_track(wall.lat, wall.lon, d, wall.tz, altitude=float(wall.z.mean()))
        n = normal_from(aspect, CFG.dip_deg)
        lit = ((n @ tr.unit_vectors().T) > 0)[None, :] & (tr.elevation[None, :] > wall.horizon_at(tr.azimuth)) & (tr.elevation[None, :] > 0)
        c = V.compare(TRUTH, area, sector, d, tr.hours, 1.0 - lit.mean(axis=0))
        mae.append(c["mae"])
        a, b = V.window_error(V.sun_window(c["grid"], c["ref"]), V.sun_window(c["grid"], c["model"]))
        if a is not None: arrive.append(a)
        if b is not None: leave.append(b)
    return float(np.mean(mae)), arrive, leave


def main() -> int:
    offsets = [0, 5, 10, 15, 20, 30, 45, 60, 90]
    table = {o: {"mae": [], "arrive": [], "leave": []} for o in offsets}
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        for name, (lat, lon) in sectors.items():
            wall = build_wall(name, lat, lon, TZ, CFG, aspect_deg=0.0)
            base = FIT[(area, name)]
            for o in offsets:
                for sign in ((1,) if o == 0 else (1, -1)):
                    mae, arrive, leave = score(wall, (base + sign * o) % 360, area, name)
                    table[o]["mae"].append(mae)
                    table[o]["arrive"] += arrive
                    table[o]["leave"] += leave
    print(f"{'error in direction':>18} {'MAE':>7} {'sun arrives':>13} {'sun leaves':>12}")
    for o in offsets:
        t = table[o]
        print(f"{o:>15} deg {np.mean(t['mae']):7.3f} {np.median(t['arrive']):9.0f} min {np.median(t['leave']):8.0f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
