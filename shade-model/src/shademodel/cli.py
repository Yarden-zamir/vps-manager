"""Sun and shade times for one climbing sector."""

from __future__ import annotations

import argparse
from datetime import date, datetime

import numpy as np

from .dem import fetch_3dep, fetch_copernicus
from .model import SectorConfig, build_sector
from .model import shade_curve as facet_shade_curve
from .wall import WallConfig, build_wall, shade_curve


def _timeline(hours: np.ndarray, shade: np.ndarray, elevation: np.ndarray) -> list[str]:
    """Collapse a shade curve into the transitions a climber reads off it."""
    up = elevation > 0
    if not up.any():
        return ["polar night"]
    state = shade[up] > 0.5
    h = hours[up]
    lines, start = [], h[0]
    for i in range(1, state.size):
        if state[i] != state[i - 1]:
            lines.append(f"{'shade' if state[i-1] else 'sun  '} {start:05.2f} - {h[i]:05.2f}")
            start = h[i]
    lines.append(f"{'shade' if state[-1] else 'sun  '} {start:05.2f} - {h[-1]:05.2f}")
    return lines


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--tz", required=True, help="IANA zone, for example Asia/Jerusalem")
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--aspect", type=float, help="compass direction the wall faces; derived from the terrain if omitted")
    p.add_argument("--height", type=float, default=25.0, help="vertical extent of the face in metres")
    p.add_argument("--dip", type=float, default=90.0, help="steepness of the face in degrees")
    p.add_argument("--lidar", action="store_true", help="use USGS 3DEP 1 m and read the wall off the grid (USA only)")
    args = p.parse_args(argv)

    day = datetime.fromisoformat(args.date).date()
    if args.lidar:
        sector = build_sector("sector", args.lat, args.lon, args.tz, SectorConfig(), fetch=fetch_3dep)
        track, shade = facet_shade_curve(sector, day)
        print(f"source: USGS 3DEP 1 m, {len(sector.facets)} facets")
    else:
        cfg = WallConfig(height_m=args.height, dip_deg=args.dip)
        wall = build_wall("sector", args.lat, args.lon, args.tz, cfg, aspect_deg=args.aspect, fetch=fetch_copernicus)
        track, shade = shade_curve(wall, day)
        given = "given" if args.aspect is not None else "from the terrain"
        print(f"source: Copernicus GLO-30, wall faces {wall.aspect_deg:.0f} deg ({given}), {args.height:.0f} m tall")

    print(f"{args.lat:.5f}, {args.lon:.5f}  {day}  {args.tz}")
    for line in _timeline(track.hours, shade, track.elevation):
        print("  " + line)
    return 0
