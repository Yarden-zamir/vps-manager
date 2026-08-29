"""Contract tests for the parts that can break silently."""

from datetime import date

import numpy as np
import pytest
from pyproj import CRS

from shademodel import terrain as T
from shademodel.dem import DemPatch
from shademodel.sun import sun_track
from shademodel.wall import WallConfig, Wall, normal_from, shade_curve

CRS_UTM = CRS.from_epsg(32636)


def flat_patch(size: int = 201, pixel: float = 1.0, height: float = 100.0) -> DemPatch:
    return DemPatch(np.full((size, size), height), 0.0, 0.0, pixel, CRS_UTM, "synthetic")


def test_flat_ground_has_no_horizon():
    p = flat_patch()  # spans x 0..200, y -200..0
    h = T.horizon(p, np.array([100.0]), np.array([-100.0]), np.array([100.0]), np.arange(0, 360, 10.0), 1.0, 50.0)
    assert np.isfinite(h).all()
    assert np.allclose(h, 0.0, atol=1e-4)  # a hair below zero: earth curvature


def test_curvature_drops_the_far_horizon():
    """Flat ground 25 km out sits below the eye by r / 2R, about a tenth of a degree.

    Only one radius falls inside the patch, so the maximum over the ray is that
    one sample and the drop is not hidden by a nearer, flatter one.
    """
    p = DemPatch(np.zeros((2001, 2001)), 0.0, 0.0, 30.0, CRS_UTM, "synthetic")
    h = T.horizon(p, np.array([30000.0]), np.array([-30000.0]), np.array([0.0]),
                  np.array([0.0]), 25000.0, 25025.0, ratio=2.0)
    expected = -np.degrees(np.arctan(25000.0 / (2 * T.EARTH_EFFECTIVE_RADIUS)))
    assert h[0, 0] == pytest.approx(expected, rel=0.05)


def test_wall_to_the_north_blocks_the_sky_at_its_own_angle():
    """A step 20 m high, 20 m north of the point, subtends 45 degrees due north."""
    p = flat_patch(size=401)
    z = np.array(p.z, copy=True)
    z[:180, :] = 120.0  # row 0 is the north edge, so this is a wall to the north
    p = DemPatch(z, 0.0, 0.0, 1.0, CRS_UTM, "synthetic")
    # the point sits at row 200, so the wall face is 20 m to the north
    x = np.array([200.0])
    y = np.array([-200.0])
    h = T.horizon(p, x, y, np.array([100.0]), np.array([0.0, 90.0, 180.0]), 1.0, 150.0)
    assert h[0, 0] == pytest.approx(45.0, abs=1.0)  # north
    assert h[0, 1] == pytest.approx(0.0, abs=0.1)  # east
    assert h[0, 2] == pytest.approx(0.0, abs=0.1)  # south


def test_slope_and_aspect_of_a_tilted_plane():
    """A plane dropping one metre per metre towards the east is 45 degrees, facing 90."""
    x = np.arange(101.0)
    p = DemPatch(np.tile(-x, (101, 1)), 0.0, 0.0, 1.0, CRS_UTM, "synthetic")
    assert T.slope_deg(p)[50, 50] == pytest.approx(45.0)
    assert T.aspect_deg(p)[50, 50] == pytest.approx(90.0)


def test_normal_points_the_way_the_wall_faces():
    n = normal_from(90.0, 90.0)  # vertical wall facing east
    assert n == pytest.approx([1.0, 0.0, 0.0], abs=1e-9)
    n = normal_from(180.0, 45.0)  # slab facing south
    assert n[1] < 0 and n[2] == pytest.approx(np.cos(np.radians(45.0)))


def test_sun_track_matches_known_solstice_at_las_vegas():
    t = sun_track(36.1556, -115.4362, date(2026, 6, 21), "America/Los_Angeles", step_minutes=5)
    up = t.elevation > 0
    assert t.hours[up][0] == pytest.approx(5.42, abs=0.15)  # sunrise about 05:25 PDT
    assert t.hours[up][-1] == pytest.approx(20.0, abs=0.15)  # sunset about 20:00 PDT
    assert t.elevation.max() == pytest.approx(77.4, abs=0.3)


def synthetic_wall(aspect: float, lat: float = 31.83, lon: float = 35.30) -> Wall:
    """A wall on open ground: no horizon, so only its own orientation shades it."""
    cfg = WallConfig()
    n_levels = cfg.n_levels
    z = 300.0 + np.arange(n_levels)
    return Wall("test", lat, lon, "Asia/Jerusalem", aspect, z,
                np.tile(normal_from(aspect, cfg.dip_deg), (n_levels, 1)),
                np.zeros((n_levels, 360)), np.arange(0, 360, 1.0), cfg)


def test_south_facing_wall_is_sunlit_all_day_at_the_winter_solstice():
    track, shade = shade_curve(synthetic_wall(180.0), date(2026, 12, 21))
    up = track.elevation > 0
    assert shade[up].max() < 0.01


def test_north_facing_wall_is_shaded_all_day_at_the_winter_solstice():
    track, shade = shade_curve(synthetic_wall(0.0), date(2026, 12, 21))
    up = track.elevation > 0
    assert shade[up].min() > 0.99


def test_east_facing_wall_turns_over_at_solar_noon():
    track, shade = shade_curve(synthetic_wall(90.0), date(2026, 3, 21))
    up = track.elevation > 0
    hours, lit = track.hours[up], shade[up] < 0.5
    assert lit[0] and not lit[-1]
    turnover = hours[np.argmax(~lit)]
    assert turnover == pytest.approx(11.9, abs=0.4)  # solar noon at 35.3 E in winter time


def test_aspect_from_a_cliff_line_picks_the_downhill_side():
    """A cliff running north to south faces either east or west."""
    from shademodel.observe import aspect_from_line

    a, b = (31.8300, 35.3000), (31.8320, 35.3000)
    assert aspect_from_line(31.831, 35.300, a, b, downhill_deg=80.0) == pytest.approx(90.0, abs=1.0)
    assert aspect_from_line(31.831, 35.300, a, b, downhill_deg=260.0) == pytest.approx(270.0, abs=1.0)


def test_aspect_from_line_rejects_two_points_on_top_of_each_other():
    from shademodel.observe import aspect_from_line

    with pytest.raises(ValueError):
        aspect_from_line(31.831, 35.300, (31.8300, 35.3000), (31.83000, 35.30000), downhill_deg=90.0)


def test_observation_parsing():
    from shademodel.observe import parse_observation

    o = parse_observation("2026-06-21:sun@12:15")
    assert (o.day, o.hour, o.into) == (date(2026, 6, 21), pytest.approx(12.25), "sun")
    whole = parse_observation("2026-12-21:shade")
    assert whole.hour is None and whole.into == "shade"
    with pytest.raises(ValueError):
        parse_observation("2026-06-21:cloudy@12:15")
