"""Red Rocks holds the only Sun Beta area with metre-scale public lidar.

It is the control experiment: it shows what the model can do when the elevation
data resolves the wall, and what is lost when only a 30 m global model exists.
"""
import itertools, json, sys, time
from datetime import date
import numpy as np
from shademodel.dem import fetch_3dep, fetch_copernicus
from shademodel.model import build_sector, shade_curve, SectorConfig
from shademodel import validate as V

TRUTH = V.load_truth("data/sunbeta_truth.json")
TZ = "America/Los_Angeles"
SECTORS = {
    "Black Corridor": (36.1555975, -115.4361525),
    "Sweet Pain Wall": (36.15597, -115.43663),
    "The Gallery": (36.15672, -115.43841),
    "The Great Red Book Area": (36.15544, -115.43461),
    "Wall of Confusion": (36.15702, -115.43904),
}
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]

def evaluate(sector_supersets, cfg):
    mae, bias, cross_err = [], [], []
    for name, sup in sector_supersets.items():
        s = sup.subset(cfg)
        for d in DAYS:
            tr, fs = shade_curve(s, d)
            r = V.compare(TRUTH, "Red Rocks", name, d, tr.hours, fs)
            mae.append(r["mae"]); bias.append(r["mean_model"] - r["mean_truth"])
            for a, b in zip(r["cross_truth"], r["cross_model"]):
                cross_err.append(abs(a - b) * 60)
    return float(np.mean(mae)), float(np.mean(bias)), (float(np.mean(cross_err)) if cross_err else float("nan"))

def supersets(fetch, pixel, patch_half, near):
    base = SectorConfig(radius_m=120, min_slope_deg=40, pixel_m=pixel, patch_half_m=patch_half,
                        near_horizon_m=near, max_facets=6000)
    out = {}
    for name, (lat, lon) in SECTORS.items():
        t0 = time.time()
        out[name] = build_sector(name, lat, lon, TZ, base, fetch=fetch)
        print(f"  built {name}: {len(out[name].facets)} facets in {time.time()-t0:.0f}s", flush=True)
    return out

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    if which == "resolution":
        for label, fetch, pixel, half, near in [
            ("3DEP 1 m", fetch_3dep, 1.0, 500, 450),
            ("3DEP 10 m", fetch_3dep, 10.0, 1500, 1400),
            ("Copernicus 30 m", fetch_copernicus, 30.0, 3000, 2900),
        ]:
            print(f"\n### {label}", flush=True)
            sup = supersets(fetch, pixel, half, near)
            for radius in (25, 40, 60, 100):
                cfg = SectorConfig(radius_m=radius, min_slope_deg=40 if pixel > 5 else 55,
                                   pixel_m=pixel, require_visible=pixel <= 5)
                m, b, c = evaluate(sup, cfg)
                print(f"  radius {radius:3d} m -> MAE {m:.3f}  bias {b:+.3f}  crossing err {c:.0f} min", flush=True)
    else:
        sup = supersets(fetch_3dep, 1.0, 500, 450)
        print(f"{'radius':>7} {'slope':>6} {'vis':>4} {'falloff':>8} {'MAE':>6} {'bias':>7} {'cross':>6}")
        for radius, slope, vis, fall in itertools.product((20, 30, 50, 80), (45, 55, 65), (True, False), (None, 25)):
            cfg = SectorConfig(radius_m=radius, min_slope_deg=slope, require_visible=vis, falloff_m=fall)
            try:
                m, b, c = evaluate(sup, cfg)
            except Exception as e:
                print(f"{radius:>7} {slope:>6} {str(vis):>4} {str(fall):>8}  failed: {e}"); continue
            print(f"{radius:>7} {slope:>6} {str(vis):>4} {str(fall):>8} {m:>6.3f} {b:>+7.3f} {c:>6.0f}", flush=True)
