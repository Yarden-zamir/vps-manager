"""Automatic sector extraction and the sun/shade curve for a climbing sector."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import numpy as np

from . import terrain as T
from .dem import CACHE, DemPatch, fetch_3dep, fetch_copernicus, to_utm
from .sun import SunTrack, sun_track

# A facet's weight is its true surface area, cell_area / cos(slope). That factor
# runs away as the slope approaches vertical, where the raster no longer resolves
# the face, so it is capped. Revisit if a lidar point cloud mesh replaces the raster.
MAX_SLOPE_FOR_WEIGHT = 85.0


@dataclass(frozen=True)
class SectorConfig:
    """How the wall of a sector is picked out of the elevation patch."""

    radius_m: float = 30.0
    falloff_m: float | None = None  # soft distance weight; None means a hard radius only
    min_slope_deg: float = 55.0
    patch_half_m: float = 500.0
    pixel_m: float = 1.0
    eye_height_m: float = 1.6
    require_visible: bool = True
    max_facets: int = 4000
    near_horizon_m: float = 450.0
    far_horizon_m: float = 30000.0
    azimuth_step_deg: float = 1.0


@dataclass
class Sector:
    name: str
    lat: float
    lon: float
    tz: str
    facets: T.Facets
    horizon: np.ndarray  # (n_facets, n_azimuth) degrees
    azimuths: np.ndarray
    config: SectorConfig
    visible: np.ndarray  # line of sight from the anchor point, per facet

    def horizon_at(self, az_deg: np.ndarray) -> np.ndarray:
        idx = az_deg / self.config.azimuth_step_deg
        i0 = np.floor(idx).astype(int) % self.azimuths.size
        i1 = (i0 + 1) % self.azimuths.size
        t = idx - np.floor(idx)
        return self.horizon[:, i0] * (1 - t) + self.horizon[:, i1] * t

    def subset(self, config: SectorConfig) -> "Sector":
        """Re-select the wall from an already built superset, without new fetches."""
        f = self.facets
        keep = (f.dist <= config.radius_m) & (f.slope >= config.min_slope_deg)
        if config.require_visible:
            keep &= self.visible
        if keep.sum() < 20:
            keep = (f.dist <= config.radius_m) & (f.slope >= config.min_slope_deg)
        sub = f.take(keep)
        if config.falloff_m:
            sub = replace(sub, weight=sub.weight * np.exp(-0.5 * (sub.dist / config.falloff_m) ** 2))
        return Sector(self.name, self.lat, self.lon, self.tz, sub, self.horizon[keep], self.azimuths, config, self.visible[keep])


def _visible_from(patch: DemPatch, ex, ey, ez, x, y, z, steps: int = 48) -> np.ndarray:
    frac = np.linspace(0.08, 0.92, steps)[None, :]
    sx = ex + (x[:, None] - ex) * frac
    sy = ey + (y[:, None] - ey) * frac
    sz = ez + (z[:, None] - ez) * frac
    ground = T.sample(patch, sx, sy)
    blocked = np.nanmax(np.where(np.isfinite(ground), ground - sz, -np.inf), axis=1)
    return blocked < 0.5  # half a metre of tolerance for raster noise


def build_sector(name, lat, lon, tz, config: SectorConfig | None = None, fetch=fetch_3dep, cache: bool = True) -> Sector:
    """Build a superset sector: every steep cell inside the largest radius of interest.

    Narrow it afterwards with `Sector.subset`, which costs nothing.
    """
    cfg = config or SectorConfig()
    key = CACHE / f"sector_{name.replace(' ','_')}_{lat:.5f}_{lon:.5f}_{cfg.radius_m:.0f}_{cfg.min_slope_deg:.0f}_{cfg.pixel_m:g}.pkl"
    if cache and key.exists():
        return pickle.loads(key.read_bytes())

    patch = fetch(lat, lon, cfg.patch_half_m, cfg.pixel_m)
    _, cx, cy = to_utm(lat, lon)
    slope = T.slope_deg(patch)
    n = T.normals(patch)
    gx, gy = patch.xy()
    dist = np.hypot(gx - cx, gy - cy)

    mask = (slope >= cfg.min_slope_deg) & (dist <= cfg.radius_m) & np.isfinite(patch.z)
    if not mask.any():
        raise RuntimeError(f"{name}: nothing steeper than {cfg.min_slope_deg} deg within {cfg.radius_m} m")

    fx, fy, fz, fn = gx[mask], gy[mask], patch.z[mask], n[mask]
    fslope, fdist = slope[mask], dist[mask]
    weight = cfg.pixel_m**2 / np.cos(np.radians(np.minimum(fslope, MAX_SLOPE_FOR_WEIGHT)))

    if fx.size > cfg.max_facets:
        pick = np.random.default_rng(0).choice(fx.size, cfg.max_facets, replace=False)
        scale = fx.size / cfg.max_facets
        fx, fy, fz, fn, fslope, fdist = (a[pick] for a in (fx, fy, fz, fn, fslope, fdist))
        weight = weight[pick] * scale

    r, c = patch.rowcol(cx, cy)
    vis = _visible_from(patch, cx, cy, patch.z[r, c] + cfg.eye_height_m, fx, fy, fz)

    facets = T.Facets(fx, fy, fz, fn, weight, fslope, fdist)
    azimuths = np.arange(0, 360, cfg.azimuth_step_deg)
    near = T.horizon(patch, fx, fy, fz, azimuths, cfg.pixel_m, cfg.near_horizon_m, ratio=1.05)
    far = far_horizon(lat, lon, azimuths, cfg)
    sector = Sector(name, lat, lon, tz, facets, np.maximum(near, far[None, :]), azimuths, cfg, vis)
    if cache:
        key.write_bytes(pickle.dumps(sector))
    return sector


def far_horizon(lat: float, lon: float, azimuths: np.ndarray, cfg: SectorConfig) -> np.ndarray:
    """Skyline of the wider landscape, from a coarse global surface model."""
    coarse = fetch_copernicus(lat, lon, cfg.far_horizon_m, 30.0)
    _, cx, cy = to_utm(lat, lon)
    r, c = coarse.rowcol(cx, cy)
    h = T.horizon(coarse, np.array([cx]), np.array([cy]), np.array([coarse.z[r, c]]), azimuths, cfg.near_horizon_m, cfg.far_horizon_m, ratio=1.08)
    return h[0]


def shade_curve(sector: Sector, day: date, step_minutes: int = 15) -> tuple[SunTrack, np.ndarray]:
    """Fraction of the sector's rock surface in shade at each time step."""
    alt = float(np.nanmean(sector.facets.z))
    track = sun_track(sector.lat, sector.lon, day, sector.tz, altitude=alt, step_minutes=step_minutes)
    s = track.unit_vectors()
    facing = sector.facets.normal @ s.T > 0.0
    above = track.elevation[None, :] > sector.horizon_at(track.azimuth)
    lit = facing & above & (track.elevation[None, :] > 0)
    w = sector.facets.weight[:, None]
    return track, 1.0 - (lit * w).sum(axis=0) / w.sum()
