"""Elevation patch retrieval.

A patch is a square of ground around a crag, projected to a local UTM zone so
that x, y and z share one metric unit. All shading maths works in that frame.
"""

from __future__ import annotations

import hashlib

import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import rasterio.warp
from pyproj import CRS, Transformer

CACHE = Path(os.environ.get("SHADE_CACHE", Path(__file__).resolve().parents[2] / "cache"))
CACHE.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DemPatch:
    """Elevation grid in a projected metric CRS. Row 0 is the north edge.

    Grid north is not true north. The sun's azimuth is a true bearing, so every
    direction taken from or given to this grid has to be corrected by the grid
    convergence. It varies by less than half a degree over a patch, so one value
    at the centre is enough.
    """

    z: np.ndarray  # metres, shape (rows, cols), NaN where no data
    x0: float  # easting of the centre of column 0
    y0: float  # northing of the centre of row 0
    pixel: float  # metre per pixel, square
    crs: CRS
    source: str
    convergence: float = 0.0  # grid bearing of true north, degrees

    def to_true(self, grid_bearing):
        """Convert a bearing measured from grid north to one from true north."""
        return (grid_bearing - self.convergence) % 360.0

    def to_grid(self, true_bearing):
        """Convert a bearing measured from true north to one from grid north."""
        return (true_bearing + self.convergence) % 360.0

    @property
    def shape(self) -> tuple[int, int]:
        return self.z.shape

    def xy(self) -> tuple[np.ndarray, np.ndarray]:
        rows, cols = self.z.shape
        x = self.x0 + self.pixel * np.arange(cols)
        y = self.y0 - self.pixel * np.arange(rows)
        return np.meshgrid(x, y)

    def rowcol(self, x: float, y: float) -> tuple[int, int]:
        return int(round((self.y0 - y) / self.pixel)), int(round((x - self.x0) / self.pixel))


def utm_crs(lat: float, lon: float) -> CRS:
    zone = int((lon + 180) // 6) + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def to_utm(lat: float, lon: float) -> tuple[CRS, float, float]:
    crs = utm_crs(lat, lon)
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x, y = tf.transform(lon, lat)
    return crs, x, y


def grid_convergence_deg(crs: CRS, lat: float, lon: float) -> float:
    """Grid bearing of true north at a point. Add it to a true bearing to get a grid one."""
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x0, y0 = tf.transform(lon, lat)
    x1, y1 = tf.transform(lon, min(lat + 0.01, 89.99))
    return float(np.degrees(np.arctan2(x1 - x0, y1 - y0)))


def _cached(key: str, suffix: str, produce) -> Path:
    path = CACHE / f"{hashlib.sha1(key.encode()).hexdigest()[:16]}{suffix}"
    if not path.exists():
        produce(path)
    return path


def fetch_3dep(lat: float, lon: float, half_m: float, pixel: float = 1.0, snap_m: float | None = None) -> DemPatch:
    """USGS 3DEP bare-earth elevation, native 1 m where lidar exists. USA only."""
    import httpx

    crs, cx, cy = to_utm(lat, lon)
    n = int(round(2 * half_m / pixel))
    if n > 8000:
        raise ValueError(f"3DEP export capped at 8000 px; asked for {n}")
    xmin, ymin = cx - half_m, cy - half_m
    xmax, ymax = cx + half_m, cy + half_m
    epsg = crs.to_epsg()
    url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
    params = {
        "bbox": f"{xmin},{ymin},{xmax},{ymax}",
        "bboxSR": epsg,
        "imageSR": epsg,
        "size": f"{n},{n}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "noDataInterpretation": "esriNoDataMatchAny",
        "f": "image",
    }
    key = f"3dep|{epsg}|{xmin:.1f}|{ymin:.1f}|{xmax:.1f}|{ymax:.1f}|{n}"

    def produce(path: Path) -> None:
        with httpx.Client(timeout=180, follow_redirects=True) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            if not r.content[:2] in (b"II", b"MM"):
                raise RuntimeError(f"3DEP returned non-tiff: {r.content[:400]!r}")
            path.write_bytes(r.content)

    path = _cached(key, ".tif", produce)
    with rasterio.open(path) as ds:
        z = ds.read(1).astype(np.float64)
        nodata = ds.nodata
        if nodata is not None:
            z[z == nodata] = np.nan
        z[z < -1000] = np.nan
        t = ds.transform
        return DemPatch(z, t.c + t.a / 2, t.f + t.e / 2, abs(t.a), crs, "USGS 3DEP 1m",
                        grid_convergence_deg(crs, lat, lon))


def copernicus_tile(lat: int, lon: int) -> Path | None:
    """Local copy of one 1x1 degree Copernicus tile, downloaded once."""
    import httpx

    url = _copernicus_tile_url(lat, lon)
    path = CACHE / url.rsplit("/", 1)[-1]
    if path.exists():
        return path
    tmp = path.with_suffix(".part")
    with httpx.Client(timeout=600, follow_redirects=True) as c:
        with c.stream("GET", url) as r:
            if r.status_code != 200:
                return None
            with tmp.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
    tmp.rename(path)
    return path


def _copernicus_tile_url(lat: int, lon: int) -> str:
    ns = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    ew = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
    name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
    return f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"


def fetch_copernicus(
    lat: float, lon: float, half_m: float, pixel: float = 30.0, snap_m: float | None = None
) -> DemPatch:
    """Copernicus GLO-30 surface model, 30 m, near global.

    The patch centre snaps to a grid of `snap_m` (default: one pixel) so that
    nearby sectors of one crag share a cached patch instead of each reprojecting
    the source tile again.
    """
    crs, cx, cy = to_utm(lat, lon)
    snap = snap_m if snap_m is not None else pixel
    cx = round(cx / snap) * snap
    cy = round(cy / snap) * snap
    cached = CACHE / f"cop_{crs.to_epsg()}_{cx:.0f}_{cy:.0f}_{half_m:.0f}_{pixel:g}.npy"
    convergence = grid_convergence_deg(crs, lat, lon)
    if cached.exists():
        z = np.load(cached)
        return DemPatch(z, cx - half_m + pixel / 2, cy + half_m - pixel / 2, pixel, crs,
                        "Copernicus GLO-30", convergence)
    deg_pad = half_m / 111000.0 * 1.6 + 0.02
    tiles = sorted(
        {
            (math.floor(la), math.floor(lo))
            for la in (lat - deg_pad, lat + deg_pad)
            for lo in (lon - deg_pad, lon + deg_pad)
        }
    )
    n = int(round(2 * half_m / pixel))
    dst = np.full((n, n), np.nan)
    dst_transform = rasterio.transform.from_origin(cx - half_m, cy + half_m, pixel, pixel)
    got = False
    for tlat, tlon in tiles:
        tile = copernicus_tile(tlat, tlon)
        if tile is None:
            continue
        try:
            with rasterio.open(tile) as ds:
                out = np.full((n, n), np.nan, dtype=np.float64)
                rasterio.warp.reproject(
                    source=rasterio.band(ds, 1),
                    destination=out,
                    dst_transform=dst_transform,
                    dst_crs=crs,
                    dst_nodata=np.nan,
                    resampling=rasterio.warp.Resampling.bilinear,
                )
        except rasterio.errors.RasterioIOError:
            continue
        good = np.isfinite(out)
        dst[good] = out[good]
        got = True
    if not got:
        raise RuntimeError(f"no Copernicus tile covers {lat},{lon}")
    np.save(cached, dst)
    return DemPatch(dst, cx - half_m + pixel / 2, cy + half_m - pixel / 2, pixel, crs,
                    "Copernicus GLO-30", convergence)
