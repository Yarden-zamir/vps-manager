"""Score the coarse-elevation wall model against Sun Beta for the Israeli crags."""
import json, sys, time
from datetime import date
import numpy as np
from shademodel.israel import TZ, matched_sectors, all_sector_positions
from shademodel.wall import WallConfig, build_wall, shade_curve
from shademodel.aspect import crag_aspects
from shademodel import validate as V

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]

def run(cfg: WallConfig, areas=None, verbose=True, mode='combined'):
    matched = matched_sectors(TRUTH_PATH, COORDS_PATH)
    rows = []
    for area, sectors in matched.items():
        if areas and area not in areas:
            continue
        positions = all_sector_positions(COORDS_PATH, area)
        aspects = crag_aspects(positions, cfg, mode=mode)
        by_position = {positions[k]: v for k, v in aspects.items()}
        for name, (lat, lon) in sectors.items():
            est = by_position[(lat, lon)]
            aspect, source = est.degrees, est.source
            w = build_wall(name, lat, lon, TZ, cfg, aspect_deg=aspect)
            per_day = []
            for d in DAYS:
                tr, fs = shade_curve(w, d)
                per_day.append(V.compare(TRUTH, area, name, d, tr.hours, fs))
            mae = float(np.mean([r["mae"] for r in per_day]))
            bias = float(np.mean([r["mean_model"] - r["mean_truth"] for r in per_day]))
            cross = [abs(a - b) * 60 for r in per_day for a, b in zip(r["cross_truth"], r["cross_model"])]
            rows.append(dict(area=area, sector=name, aspect=aspect, source=source, mae=mae,
                             bias=bias, cross=float(np.mean(cross)) if cross else float("nan")))
            if verbose:
                print(f"{area:14s} {name:22s} asp {aspect:5.0f} ({source[:4]})  MAE {mae:.3f}  bias {bias:+.3f}  cross {rows[-1]['cross']:5.0f} min", flush=True)
    return rows

def summarise(rows, label=""):
    mae = np.mean([r["mae"] for r in rows])
    cross = np.nanmean([r["cross"] for r in rows])
    bias = np.mean([r["bias"] for r in rows])
    print(f"{label}  sectors {len(rows)}  MAE {mae:.3f}  bias {bias:+.3f}  crossing {cross:.0f} min")
    for area in sorted({r['area'] for r in rows}):
        sub = [r for r in rows if r["area"] == area]
        print(f"    {area:16s} n={len(sub):2d}  MAE {np.mean([r['mae'] for r in sub]):.3f}  cross {np.nanmean([r['cross'] for r in sub]):5.0f} min")
    return mae

if __name__ == "__main__":
    modes = sys.argv[1:] or ["combined"]
    for mode in modes:
        t0 = time.time()
        rows = run(WallConfig(), verbose=len(modes) == 1, mode=mode)
        print()
        summarise(rows, f"[{mode}]")
        json.dump(rows, open(f"out/israel_rows_{mode}.json", "w"), indent=1)
        print(f"{time.time()-t0:.0f}s\n")
