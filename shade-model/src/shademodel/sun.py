"""Solar position for a day at a site."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pvlib


@dataclass(frozen=True)
class SunTrack:
    """Sun direction sampled on a local-time grid."""

    hours: np.ndarray  # local decimal hours
    elevation: np.ndarray  # degrees, refraction corrected
    azimuth: np.ndarray  # degrees clockwise from north

    def unit_vectors(self) -> np.ndarray:
        """Direction to the sun in a local east-north-up frame, shape (n, 3)."""
        el = np.radians(self.elevation)
        az = np.radians(self.azimuth)
        return np.column_stack([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), np.sin(el)])


def sun_track(
    lat: float,
    lon: float,
    day: date,
    tz: str,
    altitude: float = 0.0,
    step_minutes: int = 15,
) -> SunTrack:
    zone = ZoneInfo(tz)
    times = pd.date_range(
        start=pd.Timestamp(day, tz=zone),
        end=pd.Timestamp(day, tz=zone) + pd.Timedelta(days=1),
        freq=f"{step_minutes}min",
        inclusive="left",
    )
    sp = pvlib.solarposition.get_solarposition(times, lat, lon, altitude=altitude)
    hours = times.hour.to_numpy() + times.minute.to_numpy() / 60.0
    return SunTrack(hours, sp["apparent_elevation"].to_numpy(), sp["azimuth"].to_numpy())
