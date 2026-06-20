"""Tests de solar.geometry (zonas horarias, trayectorias, eventos del día, azimut)."""

from datetime import datetime, timedelta

import numpy as np
import pytest

from charts.sunpath import _break_wrap
from solar.geometry import (
    day_events,
    day_track,
    standard_utc_offset,
    sun_at,
    to_display_azimuth,
)


def test_standard_offset_ignores_dst():
    # Hora estándar (sin horario de verano).
    assert standard_utc_offset("America/Mexico_City") == timedelta(hours=-6)
    assert standard_utc_offset("Europe/Madrid") == timedelta(hours=1)
    assert standard_utc_offset("UTC") == timedelta(0)


def test_day_track_only_above_horizon():
    t = day_track("2026-06-21", 18.85, -99.23, "America/Mexico_City")
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
    ev = day_events("2026-03-20", 18.85, -99.23, "America/Mexico_City")
    assert ev["sunrise"] is not None and ev["sunset"] is not None
    assert ev["sunrise"] < ev["solar_noon"] < ev["sunset"]
    assert abs(ev["day_length"] - 12.0) < 0.3  # equinoccio ≈ 12 h


def test_day_events_polar_night_and_day():
    night = day_events("2026-12-21", 69.65, 18.96, "Europe/Oslo")
    assert night["polar_night"] and night["sunrise"] is None
    day = day_events("2026-06-21", 69.65, 18.96, "Europe/Oslo")
    assert day["polar_day"] and day["day_length"] == 24.0


def test_sun_at_returns_scalars():
    s = sun_at(datetime(2026, 6, 21, 12, 0), 18.85, -99.23, "America/Mexico_City")
    assert all(isinstance(v, float) for v in s.values())
    assert 0 < s["apparent_elevation"] <= 90
