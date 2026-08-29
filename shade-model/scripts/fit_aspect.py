"""Diagnostic: what wall orientation and steepness would reproduce Sun Beta's curves?

Fixes the position and the horizon, then grid searches the two numbers a 30 m
elevation model cannot supply. Separates orientation error from model error.
"""
import json, sys
from datetime import date
import numpy as np
from shademodel.israel import TZ, matched_sectors, all_sector_positions
from shademodel.aspect import crag_aspects
from shademodel.wall import WallConfig, build_wall, normal_from
from shademodel.sun import sun_track
from shademodel import validate as V

TRUTH_PATH, COORDS_PATH = "data/sunbeta_truth.json", "data/il_coords.json"
TRUTH = V.load_truth(TRUTH_PATH)
DAYS = [date(2026, m, 21) for m in (1, 3, 5, 7, 9, 11)]

def score(wall, area, sector, aspect, dip):
    tracks = []
    for d in DAYS:
        tr = sun_track(wall.lat, wall.lon, d, wall.tz, altitude=float(wall.z.mean()))
        n = normal_from(aspect, dip)
        lit = ((n @ tr.unit_vectors().T) > 0)[None, :] & (tr.elevation[None, :] > wall.horizon_at(tr.azimuth)) & (tr.elevation[None, :] > 0)
        tracks.append(V.compare(TRUTH, area, sector, d, tr.hours, 1.0 - lit.mean(axis=0))["mae"])
    return float(np.mean(tracks))

if __name__ == "__main__":
    cfg = WallConfig()
    areas = sys.argv[1:] or None
    rows = []
    for area, sectors in matched_sectors(TRUTH_PATH, COORDS_PATH).items():
        if areas and area not in areas:
            continue
        positions = all_sector_positions(COORDS_PATH, area)
        auto = {positions[k]: v for k, v in crag_aspects(positions, cfg).items()}
        for name, (lat, lon) in sectors.items():
            wall = build_wall(name, lat, lon, TZ, cfg)
            best = min(((score(wall, area, name, a, d), a, d)
                        for a in np.arange(0, 360, 5.0) for d in (60, 75, 90)), key=lambda t: t[0])
            got, src = auto[(lat, lon)]
            delta = abs((best[1] - got + 180) % 360 - 180)
            rows.append(dict(area=area, sector=name, mae_fit=best[0], aspect_fit=best[1], dip_fit=best[2],
                             aspect_auto=got, aspect_err=delta, source=src))
            print(f"{area:12s} {name:24s} fit(asp {best[1]:3.0f} dip {best[2]:2.0f}) MAE {best[0]:.3f} | auto {got:3.0f} err {delta:3.0f} deg", flush=True)
    json.dump(rows, open("out/israel_fit.json", "w"), indent=1)
    print(f"\nfitted-aspect MAE {np.mean([r['mae_fit'] for r in rows]):.3f} | aspect error mean {np.mean([r['aspect_err'] for r in rows]):.0f} median {np.median([r['aspect_err'] for r in rows]):.0f} deg")
    for area in sorted({r['area'] for r in rows}):
        sub=[r for r in rows if r['area']==area]
        print(f"  {area:14s} n={len(sub):2d} fitMAE {np.mean([r['mae_fit'] for r in sub]):.3f}  aspErr {np.mean([r['aspect_err'] for r in sub]):3.0f}  dips {sorted({int(r['dip_fit']) for r in sub})}")
