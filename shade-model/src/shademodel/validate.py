"""Compare model output against Sun Beta's published curves."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np


def load_truth(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def truth_curve(truth: dict, area: str, sector: str, day: date) -> tuple[np.ndarray, np.ndarray]:
    """Step curve as published: value[i] holds from hours[i] to hours[i+1]."""
    hours, shade = truth[area][sector][str(day.month)][str(day.day)][0]
    return np.asarray(hours, float), np.asarray(shade, float)


def truth_mean(truth: dict, area: str, sector: str, day: date) -> float:
    return float(truth[area][sector][str(day.month)][str(day.day)][1])


def on_grid(hours: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Sample a step curve on a regular grid."""
    idx = np.searchsorted(hours, grid, side="right") - 1
    return values[np.clip(idx, 0, values.size - 1)]


def crossing(grid: np.ndarray, curve: np.ndarray, level: float = 0.5) -> list[float]:
    """Times where the curve crosses a level, linearly interpolated."""
    return [t for t, _ in signed_crossings(grid, curve, level)]


def signed_crossings(grid: np.ndarray, curve: np.ndarray, level: float = 0.5) -> list[tuple[float, str]]:
    """Crossing times with the direction of travel: into the sun, or into the shade."""
    out = []
    for i in range(curve.size - 1):
        a, b = curve[i], curve[i + 1]
        if (a - level) * (b - level) < 0:
            t = float(grid[i] + (level - a) / (b - a) * (grid[i + 1] - grid[i]))
            out.append((t, "shade" if b > a else "sun"))
    return out


def compare(truth: dict, area: str, sector: str, day: date, model_hours: np.ndarray, model_shade: np.ndarray) -> dict:
    th, tv = truth_curve(truth, area, sector, day)
    grid = np.arange(th[0], th[-1] + 1e-9, 0.25)
    ref = on_grid(th, tv, grid)
    mine = np.interp(grid, model_hours, model_shade)
    return {
        "mae": float(np.abs(ref - mine).mean()),
        "mean_truth": float(ref.mean()),
        "mean_model": float(mine.mean()),
        "cross_truth": crossing(grid, ref),
        "cross_model": crossing(grid, mine),
        "grid": grid,
        "ref": ref,
        "model": mine,
    }


def sun_window(grid: np.ndarray, curve: np.ndarray, level: float = 0.5) -> tuple[float | None, float | None]:
    """When the sun first reaches the sector and when it leaves, in local hours.

    The published curves start at 08:00 and end at sunset, so a sector already
    sunlit at 08:00 reports the start of the grid.
    """
    lit = curve < level
    if not lit.any():
        return None, None
    i, j = int(np.argmax(lit)), int(len(lit) - 1 - np.argmax(lit[::-1]))
    return float(grid[i]), float(grid[j])


def window_error(ref_window, model_window) -> tuple[float | None, float | None]:
    """Minutes between the reference and the model, for arrival and departure."""
    out = []
    for a, b in zip(ref_window, model_window):
        out.append(None if a is None or b is None else abs(a - b) * 60)
    return tuple(out)
