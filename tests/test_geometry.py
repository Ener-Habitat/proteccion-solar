"""Tests de solar.geometry (trayectorias, eventos del día, hora por longitud, azimut)."""

from datetime import datetime

import numpy as np

from charts.sunpath import _break_wrap
from solar.geometry import (
    _local_to_utc,
    day_events,
    day_track,
    sun_at,
    to_display_azimuth,
)


def test_local_to_utc_offset_from_longitude():
    # Longitud −99.23° → desfase ≈ −6.6 h → UTC = local + 6.6 h.
    local = np.datetime64("2026-06-21T12:00", "s")
    utc = _local_to_utc(local, -99.23)
    off_h = (utc - local) / np.timedelta64(1, "h")
    assert abs(off_h - 99.23 / 15.0) < 1e-3  # UTC adelantado respecto a local oeste


def test_day_track_only_above_horizon():
    t = day_track("2026-06-21", 18.85, -99.23)
    assert t["azimuth"].size == t["elevation"].size == t["time_h"].size
    assert t["elevation"].min() > 0.0
    assert t["azimuth"].min() >= 0.0 and t["azimuth"].max() <= 360.0


def test_to_display_azimuth_conventions():
    az = np.array([0.0, 90.0, 180.0, 270.0])
    assert np.allclose(to_display_azimuth(az, "N0"), az)
    # S0: el Sur (180° en N0) pasa a 0°.
    assert np.allclose(to_display_azimuth(az, "S0"), [180.0, 270.0, 0.0, 90.0])


def test_break_wrap_inserts_nan_on_jump():
    az = np.array([350.0, 355.0, 5.0, 10.0])
    el = np.array([1.0, 2.0, 3.0, 4.0])
    waz, wel = _break_wrap(az, el)
    assert np.isnan(waz).sum() == 1
    assert np.isnan(wel).sum() == 1


def test_day_events_equinox_about_twelve_hours():
    ev = day_events("2026-03-20", 18.85, -99.23)
    assert ev["sunrise"] is not None and ev["sunset"] is not None
    assert ev["sunrise"] < ev["solar_noon"] < ev["sunset"]
    assert abs(ev["day_length"] - 12.0) < 0.3  # equinoccio ≈ 12 h


def test_day_events_polar_night_and_day():
    night = day_events("2026-12-21", 69.65, 18.96)
    assert night["polar_night"] and night["sunrise"] is None
    day = day_events("2026-06-21", 69.65, 18.96)
    assert day["polar_day"] and day["day_length"] == 24.0


def test_sun_at_returns_scalars():
    s = sun_at(datetime(2026, 6, 21, 12, 0), 18.85, -99.23)
    assert all(isinstance(v, float) for v in s.values())
    assert 0 < s["apparent_elevation"] <= 90
