"""Turn an elevation patch into oriented wall facets and their sky horizon."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter

from .dem import DemPatch

EARTH_EFFECTIVE_RADIUS = 6371000.0 / (1.0 - 0.13)  # curvature drop with standard refraction


def gradients(patch: DemPatch) -> tuple[np.ndarray, np.ndarray]:
    """dz/dx (east) and dz/dy (north) per cell, central differences."""
    dzdy_rows, dzdx = np.gradient(patch.z, patch.pixel)
    return dzdx, -dzdy_rows  # row index grows southward


def normals(patch: DemPatch) -> np.ndarray:
    """Upward unit normals, shape (rows, cols, 3) in east-north-up."""
    dzdx, dzdy = gradients(patch)
    n = np.stack([-dzdx, -dzdy, np.ones_like(dzdx)], axis=-1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def slope_deg(patch: DemPatch) -> np.ndarray:
    return np.degrees(np.arccos(np.clip(normals(patch)[..., 2], -1, 1)))


def aspect_deg(patch: DemPatch) -> np.ndarray:
    """Compass direction the surface faces, degrees clockwise from north."""
    n = normals(patch)
    return np.degrees(np.arctan2(n[..., 0], n[..., 1])) % 360.0


def landform_aspect(patch: DemPatch, x: float, y: float, smooth_m: float) -> float:
    """Downhill compass direction of the hillside, smoothed to the landform scale."""
    sigma = max(smooth_m / patch.pixel, 0.5)
    z = np.where(np.isfinite(patch.z), patch.z, np.nanmean(patch.z))
    sm = gaussian_filter(z, sigma)
    dzdy_rows, dzdx = np.gradient(sm, patch.pixel)
    r, c = patch.rowcol(x, y)
    return float(np.degrees(np.arctan2(-dzdx[r, c], dzdy_rows[r, c])) % 360.0)


def sample(patch: DemPatch, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear elevation at projected coordinates. NaN outside the patch."""
    rows, cols = patch.z.shape
    fc = (x - patch.x0) / patch.pixel
    fr = (patch.y0 - y) / patch.pixel
    c0 = np.floor(fc).astype(np.int64)
    r0 = np.floor(fr).astype(np.int64)
    inside = (c0 >= 0) & (r0 >= 0) & (c0 < cols - 1) & (r0 < rows - 1)
    c0 = np.clip(c0, 0, cols - 2)
    r0 = np.clip(r0, 0, rows - 2)
    tc = fc - c0
    tr = fr - r0
    z = patch.z
    v = (
        z[r0, c0] * (1 - tr) * (1 - tc)
        + z[r0, c0 + 1] * (1 - tr) * tc
        + z[r0 + 1, c0] * tr * (1 - tc)
        + z[r0 + 1, c0 + 1] * tr * tc
    )
    return np.where(inside, v, np.nan)


def sample_nearest(patch: DemPatch, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Nearest-cell elevation. Cheaper than bilinear and enough for ray marching."""
    rows, cols = patch.z.shape
    c = np.rint((x - patch.x0) / patch.pixel).astype(np.int32)
    r = np.rint((patch.y0 - y) / patch.pixel).astype(np.int32)
    ok = (c >= 0) & (r >= 0) & (c < cols) & (r < rows)
    np.clip(c, 0, cols - 1, out=c)
    np.clip(r, 0, rows - 1, out=r)
    return np.where(ok, patch.z[r, c], np.nan)


def ray_radii(start: float, stop: float, ratio: float) -> np.ndarray:
    n = max(1, int(np.ceil(np.log(stop / start) / np.log(ratio))))
    return start * ratio ** np.arange(n + 1)


def horizon(
    patch: DemPatch,
    px: np.ndarray,
    py: np.ndarray,
    pz: np.ndarray,
    azimuths: np.ndarray,
    r_start: float,
    r_stop: float,
    ratio: float = 1.05,
) -> np.ndarray:
    """Largest sky-blocking angle per point and azimuth, in degrees.

    Marches outward over the patch and keeps the steepest line of sight. A point
    that sits on a wall sees the wall above it, so this one pass covers both the
    face's own shape and shadows cast by anything around it.
    """
    radii = ray_radii(r_start, r_stop, ratio)
    az = np.radians(azimuths).astype(np.float32)
    sin_az, cos_az = np.sin(az), np.cos(az)
    px = px.astype(np.float64)
    py = py.astype(np.float64)
    pz = pz.astype(np.float32)
    best = np.full((px.size, azimuths.size), -np.inf, dtype=np.float32)
    zgrid = patch.z
    for r in radii:
        drop = r * r / (2 * EARTH_EFFECTIVE_RADIUS)
        x = px[:, None] + (r * sin_az)[None, :]
        y = py[:, None] + (r * cos_az)[None, :]
        zs = sample_nearest(patch, x, y).astype(np.float32)
        tan = (zs - drop - pz[:, None]) / np.float32(r)
        np.maximum(best, np.where(np.isfinite(tan), tan, -np.inf), out=best)
    best[~np.isfinite(best)] = 0.0
    return np.degrees(np.arctan(best)).astype(np.float64)


@dataclass(frozen=True)
class Facets:
    """A set of oriented surface samples that stand in for a climbing sector."""

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    normal: np.ndarray  # (n, 3) east-north-up unit vectors
    weight: np.ndarray  # true surface area represented, m^2
    slope: np.ndarray  # degrees from horizontal
    dist: np.ndarray  # metres from the sector's anchor point

    def __len__(self) -> int:
        return self.x.size

    def take(self, keep: np.ndarray) -> "Facets":
        return Facets(*(a[keep] for a in (self.x, self.y, self.z, self.normal, self.weight, self.slope, self.dist)))
