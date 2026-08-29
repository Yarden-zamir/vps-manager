"""Sun and shade times for a climbing sector, and the wall direction they need."""

from __future__ import annotations

import argparse
from datetime import date, datetime

import numpy as np

from .dem import fetch_3dep, fetch_copernicus
from .model import SectorConfig, build_sector
from .model import shade_curve as facet_shade_curve
from .observe import aspect_from_line, aspect_from_observations, parse_observation, terrain_aspect
from .photo import combine, read_photo
from .wall import WallConfig, build_wall, shade_curve


def _point(text: str) -> tuple[float, float]:
    lat, _, lon = text.partition(",")
    return float(lat), float(lon)


def _timeline(hours: np.ndarray, shade: np.ndarray, elevation: np.ndarray) -> list[str]:
    """Collapse a shade curve into the transitions a climber reads off it."""
    up = elevation > 0
    if not up.any():
        return ["the sun does not rise"]
    state = shade[up] > 0.5
    h = hours[up]
    lines, start = [], h[0]
    for i in range(1, state.size):
        if state[i] != state[i - 1]:
            lines.append(f"{'shade' if state[i - 1] else 'sun  '} {start:05.2f} - {h[i]:05.2f}")
            start = h[i]
    lines.append(f"{'shade' if state[-1] else 'sun  '} {start:05.2f} - {h[-1]:05.2f}")
    return lines


def _times(args) -> int:
    day = datetime.fromisoformat(args.date).date()
    if args.lidar:
        sector = build_sector("sector", args.lat, args.lon, args.tz, SectorConfig(), fetch=fetch_3dep)
        track, shade = facet_shade_curve(sector, day)
        print(f"source: USGS 3DEP 1 m, wall read from the grid, {len(sector.facets)} facets")
    else:
        cfg = WallConfig(height_m=args.height, dip_deg=args.dip)
        wall = build_wall("sector", args.lat, args.lon, args.tz, cfg, aspect_deg=args.aspect, fetch=fetch_copernicus)
        track, shade = shade_curve(wall, day)
        origin = "given" if args.aspect is not None else "from the terrain, expect 50 deg of error"
        print(f"source: Copernicus GLO-30, wall faces {wall.aspect_deg:.0f} deg ({origin}), {args.height:.0f} m tall")
    print(f"{args.lat:.5f}, {args.lon:.5f}  {day}  {args.tz}")
    for line in _timeline(track.hours, shade, track.elevation):
        print("  " + line)
    return 0


def _aspect(args) -> int:
    from_photo = None
    if args.photo:
        fixes = [read_photo(path, args.declination) for path in args.photo]
        for f in fixes:
            if f.camera_deg is None:
                print(f"  {f.path}: no camera direction in the EXIF, skipped")
            elif f.direction_ref == "M" and args.declination == 0.0:
                print(f"  {f.path}: heading is magnetic; pass --declination (about 4.6 over Israel)")
        located = [f for f in fixes if f.lat is not None]
        if args.lat is None and located:
            args.lat, args.lon = located[0].lat, located[0].lon
        from_photo = combine([f for f in fixes if f.facing_deg is not None])
    if args.lat is None:
        raise SystemExit("give --lat and --lon, or a photo whose EXIF carries a position")

    if args.along:
        if len(args.along) != 2:
            raise SystemExit("--along takes exactly two points along the cliff")
        value = aspect_from_line(args.lat, args.lon, args.along[0], args.along[1])
        print(f"{value:.0f} deg  (from the cliff line; expect about 15 deg of error)")
    elif args.saw:
        fit = aspect_from_observations(args.lat, args.lon, args.tz,
                                       [parse_observation(s) for s in args.saw], prior_deg=from_photo)
        seed = "a photo heading" if from_photo is not None else "the terrain"
        print(f"{fit.degrees:.0f} deg  (from {len(args.saw)} observation(s), seeded with {seed}; "
              f"directions within tolerance span {fit.spread_deg:.0f} deg)")
        if fit.spread_deg > 20:
            print("  add an observation from the opposite season to narrow this")
    elif from_photo is not None:
        print(f"{from_photo:.0f} deg  (from {len(args.photo)} photo(s); a phone compass is good to 10-20 deg)")
    else:
        print(f"{terrain_aspect(args.lat, args.lon):.0f} deg  (downhill direction only; expect 50 deg of error)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command")

    t = sub.add_parser("times", help="sun and shade times for a day")
    t.add_argument("--lat", type=float, required=True)
    t.add_argument("--lon", type=float, required=True)
    t.add_argument("--tz", required=True, help="IANA zone, for example Asia/Jerusalem")
    t.add_argument("--date", default=date.today().isoformat())
    t.add_argument("--aspect", type=float, help="compass direction the wall faces")
    t.add_argument("--height", type=float, default=25.0, help="vertical extent of the face in metres")
    t.add_argument("--dip", type=float, default=90.0, help="steepness of the face in degrees")
    t.add_argument("--lidar", action="store_true", help="read the wall off USGS 3DEP 1 m (USA only)")
    t.set_defaults(func=_times)

    a = sub.add_parser("aspect", help="work out which way the wall faces")
    a.add_argument("--lat", type=float, help="omit when a photo carries the position")
    a.add_argument("--lon", type=float)
    a.add_argument("--tz", default="UTC", help="needed with --saw")
    a.add_argument("--photo", action="append",
                   help="image taken from the foot of the sector facing the rock; repeatable")
    a.add_argument("--declination", type=float, default=0.0,
                   help="magnetic declination to add when the EXIF heading is magnetic, east positive")
    a.add_argument("--along", type=_point, action="append",
                   help="lat,lon of a point along the cliff; give it twice")
    a.add_argument("--saw", action="append",
                   help="what you saw, as DATE:sun@HH:MM or DATE:shade@HH:MM, "
                        "or DATE:shade for a whole day; repeatable")
    a.set_defaults(func=_aspect)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 2
    return args.func(args)
