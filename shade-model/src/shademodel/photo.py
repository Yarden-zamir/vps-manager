"""Read what a phone photo already knows about a wall.

A photo taken from the foot of a sector, facing the rock, carries four things in
its EXIF: where the photographer stood, which way the camera pointed, when the
shutter opened, and, to whoever looks at it, whether the wall was in the sun.

The camera direction is the wall's facing direction turned by 180 degrees. That is
the one number the coarse elevation model cannot supply, and it arrives for free
with a photo anybody can already take.

Phone compasses are good to roughly ten to twenty degrees, which is inside the
budget for half-hour timing. Watch two things: a photo taken side on to the wall
reports a direction along the cliff rather than into it, and a heading written
against magnetic north needs the local declination added.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

_GPS = {name: tag for tag, name in ExifTags.GPSTAGS.items()}
_DATETIME_ORIGINAL = 36867


@dataclass(frozen=True)
class PhotoFix:
    """What one photo pins down."""

    path: str
    lat: float | None
    lon: float | None
    facing_deg: float | None  # direction the wall faces, true north
    camera_deg: float | None  # direction the camera pointed, true north
    taken: datetime | None
    direction_ref: str  # "T" true, "M" magnetic, "" absent

    @property
    def usable(self) -> bool:
        return self.lat is not None and self.facing_deg is not None


def _degrees(value) -> float:
    d, m, s = (float(v) for v in value)
    return d + m / 60.0 + s / 3600.0


def read_photo(path: str | Path, declination_deg: float = 0.0) -> PhotoFix:
    """Position, camera heading and time from one image.

    `declination_deg` is added when the heading was written against magnetic north.
    East is positive: about +4.6 degrees over Israel.
    """
    with Image.open(path) as img:
        exif = img.getexif()
        gps = exif.get_ifd(ExifTags.IFD.GPSInfo) or {}
        taken_raw = exif.get_ifd(ExifTags.IFD.Exif).get(_DATETIME_ORIGINAL) or exif.get(_DATETIME_ORIGINAL)

    lat = lon = None
    if _GPS["GPSLatitude"] in gps and _GPS["GPSLongitude"] in gps:
        lat = _degrees(gps[_GPS["GPSLatitude"]])
        lon = _degrees(gps[_GPS["GPSLongitude"]])
        if str(gps.get(_GPS["GPSLatitudeRef"], "N")).upper().startswith("S"):
            lat = -lat
        if str(gps.get(_GPS["GPSLongitudeRef"], "E")).upper().startswith("W"):
            lon = -lon

    ref = str(gps.get(_GPS["GPSImgDirectionRef"], "")).upper()[:1]
    camera = gps.get(_GPS["GPSImgDirection"])
    camera_deg = facing = None
    if camera is not None:
        camera_deg = float(camera) + (declination_deg if ref == "M" else 0.0)
        camera_deg %= 360.0
        facing = (camera_deg + 180.0) % 360.0  # the wall looks back at the camera

    taken = None
    if taken_raw:
        try:
            taken = datetime.strptime(str(taken_raw), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            taken = None

    return PhotoFix(str(path), lat, lon, facing, camera_deg, taken, ref)


def combine(fixes: list[PhotoFix]) -> float:
    """Mean facing direction of several photos of the same wall."""
    import numpy as np

    angles = np.radians([f.facing_deg for f in fixes if f.facing_deg is not None])
    if not angles.size:
        raise ValueError("no photo carried a camera direction")
    return float(np.degrees(np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())) % 360.0)
