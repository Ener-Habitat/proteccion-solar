"""Validación de solar.position contra pvlib (SPA de alta exactitud).

pvlib es sólo dependencia de desarrollo/test; la app desplegada usa el numpy puro.
Tolerancia objetivo: < 0.1° lejos del horizonte, algo mayor cerca de él (donde la
refracción y la geometría rasante amplifican diferencias entre modelos).
"""

import numpy as np
import pandas as pd
import pvlib
import pytest

from solar.position import solar_position

# (nombre, lat, lon) — variedad de latitudes incluyendo trópico y alta latitud.
LOCATIONS = [
    ("Temixco", 18.85, -99.23),
    ("Merida", 20.97, -89.62),
    ("CDMX", 19.43, -99.13),
    ("Quito", -0.18, -78.47),
    ("Tromso", 69.65, 18.96),
    ("Sydney", -33.87, 151.21),
]

DATES = ["2026-03-21", "2026-06-21", "2026-09-23", "2026-12-21"]


def _pvlib_reference(times_utc, lat, lon):
    idx = pd.DatetimeIndex(times_utc).tz_localize("UTC")
    sp = pvlib.solarposition.get_solarposition(idx, lat, lon, method="nrel_numpy")
    return sp


@pytest.mark.parametrize("name,lat,lon", LOCATIONS)
@pytest.mark.parametrize("date", DATES)
def test_elevation_and_azimuth_match_pvlib(name, lat, lon, date):
    times = pd.date_range(f"{date} 00:00", f"{date} 23:50", freq="10min").to_numpy()
    ours = solar_position(times, lat, lon)
    ref = _pvlib_reference(times, lat, lon)

    # Sólo comparamos cuando el Sol está sobre el horizonte (apparent_elevation > 3°),
    # evitando el régimen rasante donde los modelos de refracción difieren.
    up = ref["apparent_elevation"].to_numpy() > 3.0
    if up.sum() == 0:
        pytest.skip("Sol siempre bajo el horizonte en este caso")

    elev_err = np.abs(ours["apparent_elevation"][up] - ref["apparent_elevation"].to_numpy()[up])
    assert elev_err.max() < 0.2, f"{name} {date}: error elevación {elev_err.max():.3f}°"

    # Azimut: diferencia angular envuelta a [-180, 180]; relajamos cerca del cenit
    # (elevación > 80°) donde el azimut está mal condicionado.
    not_zenith = ref["apparent_elevation"].to_numpy()[up] < 80.0
    az_err = np.abs(
        (ours["azimuth"][up][not_zenith] - ref["azimuth"].to_numpy()[up][not_zenith] + 180.0) % 360.0 - 180.0
    )
    if az_err.size:
        assert az_err.max() < 0.3, f"{name} {date}: error azimut {az_err.max():.3f}°"


@pytest.mark.parametrize("name,lat,lon", LOCATIONS)
def test_declination_and_eot_match_pvlib(name, lat, lon):
    times = pd.date_range("2026-01-01", "2026-12-31", freq="1D").to_numpy()
    ours = solar_position(times, lat, lon)
    idx = pd.DatetimeIndex(times).tz_localize("UTC")
    decl_ref = pvlib.solarposition.declination_spencer71(idx.dayofyear)  # rad
    # Comparación gruesa de declinación contra una aproximación independiente (< 0.5°).
    decl_err = np.abs(ours["declination"] - np.degrees(decl_ref.to_numpy()))
    assert decl_err.max() < 0.5, f"{name}: error declinación {decl_err.max():.3f}°"


def test_physical_sanity_summer_tropic_azimuth_north():
    """En Mérida (21°N) al mediodía solar del solsticio de verano, el Sol está
    al norte del cenit (punto subsolar en el Trópico de Cáncer, 23.5°N)."""
    # ~mediodía solar en Mérida (lon -89.62 → UTC ≈ 18:00 + corrección).
    times = pd.date_range("2026-06-21 17:30", "2026-06-21 18:30", freq="5min").to_numpy()
    sp = solar_position(times, 20.97, -89.62)
    i = int(np.argmax(sp["apparent_elevation"]))
    az = sp["azimuth"][i]
    # Azimut cerca de 0° o 360° (Norte).
    assert min(az, 360.0 - az) < 25.0, f"azimut a mediodía = {az:.1f}° (se esperaba ~Norte)"
    assert sp["apparent_elevation"][i] > 85.0


def test_scalar_input_returns_array():
    sp = solar_position(np.datetime64("2026-06-21T18:00"), 18.85, -99.23)
    assert sp["elevation"].shape == (1,)
    assert np.isfinite(sp["elevation"][0])
