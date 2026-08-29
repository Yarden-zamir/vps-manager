"""Head to head against Sun Beta: curves, daily means and sun window times."""
import json, sys
from datetime import date
import numpy as np
from shademodel.israel import TZ, matched_sectors, all_sector_positions
from shademodel.wall import WallConfig, build_wall, shade_curve
from shademodel.aspect import crag_aspects
from shademodel import validate as V

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
FIT = {(r["area"], r["sector"]): r["aspect_fit"] for r in json.load(open("out/israel_fit.json"))}
CFG = WallConfig()


def rows(aspect_mode: str):
    """aspect_mode: 'auto' derives it, 'given' uses one supplied number per sector."""
    out = []
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        positions = all_sector_positions(COORDS_PATH, area)
        auto = {positions[k]: v for k, v in crag_aspects(positions, CFG).items()}
        for name, (lat, lon) in sectors.items():
            aspect = FIT[(area, name)] if aspect_mode == "given" else auto[(lat, lon)].degrees
            source = "given" if aspect_mode == "given" else auto[(lat, lon)].source
            w = build_wall(name, lat, lon, TZ, CFG, aspect_deg=aspect)
            mae, arrive, leave, curves = [], [], [], {}
            for d in DAYS:
                tr, fs = shade_curve(w, d)
                c = V.compare(TRUTH, area, name, d, tr.hours, fs)
                mae.append(c["mae"])
                a, b = V.window_error(V.sun_window(c["grid"], c["ref"]), V.sun_window(c["grid"], c["model"]))
                if a is not None: arrive.append(a)
                if b is not None: leave.append(b)
                curves[d.isoformat()] = dict(hours=c["grid"].tolist(), truth=c["ref"].tolist(), model=c["model"].tolist())
            out.append(dict(area=area, sector=name, aspect=aspect, source=source,
                            mae=float(np.mean(mae)),
                            arrive_err=float(np.median(arrive)) if arrive else None,
                            leave_err=float(np.median(leave)) if leave else None,
                            curves=curves))
    return out


def table(rs, label):
    print(f"\n=== {label} ===")
    print(f"{'crag':14s} {'n':>2} {'MAE':>6} {'sun arrives':>12} {'sun leaves':>11}")
    for area in sorted({r["area"] for r in rs}):
        sub = [r for r in rs if r["area"] == area]
        arr = [r["arrive_err"] for r in sub if r["arrive_err"] is not None]
        lev = [r["leave_err"] for r in sub if r["leave_err"] is not None]
        print(f"{area:14s} {len(sub):2d} {np.mean([r['mae'] for r in sub]):6.3f} "
              f"{np.median(arr):8.0f} min {np.median(lev):7.0f} min")
    arr = [r["arrive_err"] for r in rs if r["arrive_err"] is not None]
    lev = [r["leave_err"] for r in rs if r["leave_err"] is not None]
    print(f"{'ALL':14s} {len(rs):2d} {np.mean([r['mae'] for r in rs]):6.3f} "
          f"{np.median(arr):8.0f} min {np.median(lev):7.0f} min")


if __name__ == "__main__":
    auto = rows("auto")
    given = rows("given")
    json.dump({"auto": auto, "given": given}, open("out/report.json", "w"))
    table(auto, "azimuth derived automatically")
    table(given, "azimuth supplied, one number per sector")
    print("\nper sector, automatic:")
    for r in sorted(auto, key=lambda r: -r["mae"]):
        print(f"  {r['area']:12s} {r['sector']:26s} {r['source']:11s} asp {r['aspect']:5.0f}  MAE {r['mae']:.3f}")
