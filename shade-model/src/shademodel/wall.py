"""A wall model for sectors whose elevation data is too coarse to hold the cliff.

Outside the USA and a few national lidar programmes, the best free elevation
model is Copernicus GLO-30 at 30 m. A 30 m grid smooths a 30 m crag into a
40 degree hillside, so the face itself has to come from somewhere else:

  * where the wall faces  -> downhill direction of the landform around the crag
  * how steep it stands   -> a prior; a sport crag is near vertical by definition
  * how tall it is        -> a prior, or the longest route at the sector

Everything the grid still does hold, the shape of the valley and the skyline,
comes from the same ray march used by the high resolution model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from . import terrain as T
from .terrain import landform_aspect
from .dem import DemPatch, fetch_copernicus, to_utm
from .sun import SunTrack, sun_track


@dataclass(frozen=True)
class WallConfig:
    height_m: float = 25.0  # vertical extent of the climbable face
    n_levels: int = 9  # sample points up the face
    dip_deg: float = 90.0  # steepness prior, 90 is dead vertical
    aspect_smooth_m: float = 45.0  # landform scale used for the downhill direction
    strike_radius_m: float = 250.0  # neighbouring sectors that trace the same cliff
    min_neighbours: int = 2
    base_offset_m: float = 0.0  # push the base out from the point along the aspect
    patch_half_m: float = 4000.0
    pixel_m: float = 30.0
    near_horizon_m: float = 4000.0  # end of the fine patch
    far_horizon_m: float = 40000.0  # end of the coarse skyline patch
    far_pixel_m: float = 200.0
    azimuth_step_deg: float = 1.0


@dataclass
class Wall:
    name: str
    lat: float
    lon: float
    tz: str
    aspect_deg: float
    z: np.ndarray  # elevation of each sample up the face
    normal: np.ndarray  # (n_levels, 3), identical rows unless the dip varies
    horizon: np.ndarray  # (n_levels, n_azimuth) degrees
    azimuths: np.ndarray
    config: WallConfig

    def horizon_at(self, az_deg: np.ndarray) -> np.ndarray:
        idx = az_deg / self.config.azimuth_step_deg
        i0 = np.floor(idx).astype(int) % self.azimuths.size
        i1 = (i0 + 1) % self.azimuths.size
        t = idx - np.floor(idx)
        return self.horizon[:, i0] * (1 - t) + self.horizon[:, i1] * t


def normal_from(aspect_deg: float, dip_deg: float) -> np.ndarray:
    a, d = np.radians(aspect_deg), np.radians(dip_deg)
    return np.array([np.sin(a) * np.sin(d), np.cos(a) * np.sin(d), np.cos(d)])


def build_wall(
    name: str,
    lat: float,
    lon: float,
    tz: str,
    config: WallConfig | None = None,
    aspect_deg: float | None = None,
    fetch=fetch_copernicus,
) -> Wall:
    cfg = config or WallConfig()
    patch = fetch(lat, lon, cfg.patch_half_m, cfg.pixel_m, snap_m=300.0)
    _, cx, cy = to_utm(lat, lon)
    if aspect_deg is None:
        aspect_deg = landform_aspect(patch, cx, cy, cfg.aspect_smooth_m)

    a = np.radians(aspect_deg)
    bx = cx + cfg.base_offset_m * np.sin(a)
    by = cy + cfg.base_offset_m * np.cos(a)
    r, c = patch.rowcol(bx, by)
    z0 = float(patch.z[r, c])

    levels = (np.arange(cfg.n_levels) + 0.5) / cfg.n_levels * cfg.height_m
    z = z0 + levels
    n = np.tile(normal_from(aspect_deg, cfg.dip_deg), (cfg.n_levels, 1))

    azimuths = np.arange(0, 360, cfg.azimuth_step_deg)
    px = np.full(cfg.n_levels, bx)
    py = np.full(cfg.n_levels, by)
    near = T.horizon(patch, px, py, z, azimuths, cfg.pixel_m / 2, cfg.near_horizon_m, ratio=1.05)
    coarse = fetch(lat, lon, cfg.far_horizon_m, cfg.far_pixel_m, snap_m=2000.0)
    far = T.horizon(coarse, px[:1], py[:1], z[:1], azimuths, cfg.near_horizon_m, cfg.far_horizon_m, ratio=1.08)
    return Wall(name, lat, lon, tz, aspect_deg, z, n, np.maximum(near, far), azimuths, cfg)


def shade_curve(wall: Wall, day: date, step_minutes: int = 15) -> tuple[SunTrack, np.ndarray]:
    track = sun_track(wall.lat, wall.lon, day, wall.tz, altitude=float(wall.z.mean()), step_minutes=step_minutes)
    s = track.unit_vectors()
    facing = wall.normal @ s.T > 0.0
    above = track.elevation[None, :] > wall.horizon_at(track.azimuth)
    lit = facing & above & (track.elevation[None, :] > 0)
    return track, 1.0 - lit.mean(axis=0)
