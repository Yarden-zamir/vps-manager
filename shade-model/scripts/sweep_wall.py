"""Sensitivity of the non-orientation part of the model.

Runs with the fitted orientation so the sweep sees only the wall's height,
sampling and steepness, not the azimuth error that dominates everything else.
"""
import itertools, json
from datetime import date
import numpy as np
from shademodel.israel import TZ, matched_sectors
from shademodel.wall import WallConfig, build_wall, shade_curve
from shademodel import validate as V

TRUTH = V.load_truth("data/sunbeta_truth.json")
FIT = {(r["area"], r["sector"]): r["aspect_fit"] for r in json.load(open("out/israel_fit.json"))}
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]
MATCHED = matched_sectors("data/sunbeta_truth.json", "data/il_coords.json")

def evaluate(cfg, areas=None):
    out = []
    for area, sectors in MATCHED.items():
        if areas and area not in areas: continue
        for name, (lat, lon) in sectors.items():
            w = build_wall(name, lat, lon, TZ, cfg, aspect_deg=FIT[(area, name)])
            for d in DAYS:
                tr, fs = shade_curve(w, d)
                out.append(V.compare(TRUTH, area, name, d, tr.hours, fs)["mae"])
    return float(np.mean(out))

LINEAR = ["Ein Fara", "Gita East", "Zanoah", "Shilat", "Beit Arye"]
print(f"{'height':>6} {'levels':>6} {'dip':>4} {'base drop':>9} {'MAE all':>8} {'MAE linear':>11}")
for h, lv, dip, drop in itertools.product((15, 25, 40, 60), (5, 9), (80, 90), (0.0,)):
    cfg = WallConfig(height_m=h, n_levels=lv, dip_deg=dip)
    print(f"{h:6d} {lv:6d} {dip:4d} {drop:9.0f} {evaluate(cfg):8.3f} {evaluate(cfg, LINEAR):11.3f}", flush=True)
