"""Posición solar aparente — algoritmo NOAA / Jean Meeus, en numpy puro.

Sin dependencias pesadas (no pvlib, no scipy): sólo ``numpy`` y la librería estándar.
Las ecuaciones son las del *NOAA Solar Calculator* (basadas en Meeus, *Astronomical
Algorithms*), con exactitud típica < 0.1° para fechas en el rango 1900–2100. Se expone
cada paso intermedio (declinación, ecuación del tiempo, ángulo horario) para que la app
educativa pueda mostrar las fórmulas con sus valores actuales.

Convención de azimut: **Norte = 0°, sentido horario** (E=90°, S=180°, W=270°), igual que
pvlib/NOAA. La conversión a "Sur = 0°" se hace en la capa de presentación.

Referencia: https://gml.noaa.gov/grad/solcalc/solareqns.PDF
"""

from __future__ import annotations

import numpy as np

# Época J2000.0 en día juliano y días por siglo juliano.
_JD_J2000 = 2451545.0
_DAYS_PER_CENTURY = 36525.0
# Día juliano del epoch Unix (1970-01-01T00:00:00Z).
_JD_UNIX_EPOCH = 2440587.5
_SECONDS_PER_DAY = 86400.0


def to_julian_day(times_utc) -> np.ndarray:
    """Convierte tiempos UTC a día juliano (float).

    ``times_utc`` puede ser un ``numpy.datetime64``, un array de ellos, un
    ``datetime`` de la stdlib o un ``pandas.DatetimeIndex``. Se interpreta en UTC.
    Se usa el epoch Unix como referencia exacta, evitando aritmética de calendario.
    """
    t = np.asarray(times_utc, dtype="datetime64[ns]")
    unix_seconds = t.astype("datetime64[ns]").astype("int64") / 1e9
    return unix_seconds / _SECONDS_PER_DAY + _JD_UNIX_EPOCH


def _utc_minutes_of_day(times_utc) -> np.ndarray:
    """Minutos transcurridos del día UTC (0–1440), con fracción."""
    t = np.asarray(times_utc, dtype="datetime64[ns]")
    day = t.astype("datetime64[D]").astype("datetime64[ns]")
    seconds = (t - day).astype("timedelta64[ns]").astype("int64") / 1e9
    return seconds / 60.0


def solar_position(times_utc, latitude: float, longitude: float) -> dict:
    """Posición solar para uno o varios instantes en una geolocalización.

    Parameters
    ----------
    times_utc : datetime64 / array / datetime / DatetimeIndex
        Instante(s) en **UTC**.
    latitude : float
        Latitud en grados (Norte positivo).
    longitude : float
        Longitud en grados (Este positivo, Oeste negativo).

    Returns
    -------
    dict de ``numpy.ndarray`` (grados salvo donde se indique):
        ``apparent_elevation`` — elevación con refracción atmosférica
        ``elevation``          — elevación geométrica (sin refracción)
        ``zenith``             — ángulo cenital geométrico (90 − elevation)
        ``azimuth``            — azimut (N=0°, horario)
        ``declination``        — declinación solar δ
        ``equation_of_time``   — ecuación del tiempo (minutos)
        ``hour_angle``         — ángulo horario H
    """
    jd = to_julian_day(times_utc)
    minutes = _utc_minutes_of_day(times_utc)

    # Siglo juliano desde J2000.
    T = (jd - _JD_J2000) / _DAYS_PER_CENTURY

    # --- Geometría de la órbita terrestre (todo en grados) ---
    # Longitud media geométrica del Sol.
    L0 = np.mod(280.46646 + T * (36000.76983 + 0.0003032 * T), 360.0)
    # Anomalía media del Sol.
    M = 357.52911 + T * (35999.05029 - 0.0001537 * T)
    # Excentricidad de la órbita terrestre.
    e = 0.016708634 - T * (0.000042037 + 0.0000001267 * T)

    Mrad = np.radians(M)
    # Ecuación del centro.
    C = (
        np.sin(Mrad) * (1.914602 - T * (0.004817 + 0.000014 * T))
        + np.sin(2 * Mrad) * (0.019993 - 0.000101 * T)
        + np.sin(3 * Mrad) * 0.000289
    )
    true_long = L0 + C
    # Longitud aparente (corrección por nutación y aberración).
    omega = 125.04 - 1934.136 * T
    app_long = true_long - 0.00569 - 0.00478 * np.sin(np.radians(omega))

    # Oblicuidad de la eclíptica.
    mean_obliq = 23.0 + (26.0 + (21.448 - T * (46.815 + T * (0.00059 - T * 0.001813))) / 60.0) / 60.0
    obliq_corr = mean_obliq + 0.00256 * np.cos(np.radians(omega))

    # --- Declinación solar ---
    declination = np.degrees(
        np.arcsin(np.sin(np.radians(obliq_corr)) * np.sin(np.radians(app_long)))
    )

    # --- Ecuación del tiempo (minutos) ---
    y = np.tan(np.radians(obliq_corr / 2.0)) ** 2
    L0rad = np.radians(L0)
    eot = 4.0 * np.degrees(
        y * np.sin(2 * L0rad)
        - 2 * e * np.sin(Mrad)
        + 4 * e * y * np.sin(Mrad) * np.cos(2 * L0rad)
        - 0.5 * y * y * np.sin(4 * L0rad)
        - 1.25 * e * e * np.sin(2 * Mrad)
    )

    # --- Tiempo solar verdadero y ángulo horario ---
    # Trabajamos en UTC, así que el desfase horario es 0 y sólo corrige la longitud.
    true_solar_time = np.mod(minutes + eot + 4.0 * longitude, 1440.0)
    hour_angle = true_solar_time / 4.0 - 180.0
    hour_angle = np.where(hour_angle < -180.0, hour_angle + 360.0, hour_angle)

    # --- Ángulo cenital y elevación ---
    lat_rad = np.radians(latitude)
    decl_rad = np.radians(declination)
    H_rad = np.radians(hour_angle)
    cos_zenith = (
        np.sin(lat_rad) * np.sin(decl_rad)
        + np.cos(lat_rad) * np.cos(decl_rad) * np.cos(H_rad)
    )
    cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
    zenith = np.degrees(np.arccos(cos_zenith))
    elevation = 90.0 - zenith

    # --- Azimut (N=0°, horario) ---
    sin_zenith = np.sin(np.radians(zenith))
    # Evita división por cero en el cenit/nadir.
    safe = sin_zenith > 1e-9
    cos_az = np.where(
        safe,
        (np.sin(lat_rad) * np.cos(np.radians(zenith)) - np.sin(decl_rad))
        / np.where(safe, np.cos(lat_rad) * sin_zenith, 1.0),
        0.0,
    )
    cos_az = np.clip(cos_az, -1.0, 1.0)
    az_core = np.degrees(np.arccos(cos_az))
    azimuth = np.where(hour_angle > 0.0, np.mod(az_core + 180.0, 360.0),
                       np.mod(540.0 - az_core, 360.0))

    apparent_elevation = elevation + _refraction_correction(elevation)

    return {
        "apparent_elevation": np.atleast_1d(apparent_elevation),
        "elevation": np.atleast_1d(elevation),
        "zenith": np.atleast_1d(zenith),
        "azimuth": np.atleast_1d(azimuth),
        "declination": np.atleast_1d(declination),
        "equation_of_time": np.atleast_1d(eot),
        "hour_angle": np.atleast_1d(hour_angle),
    }


def _refraction_correction(elevation_deg: np.ndarray) -> np.ndarray:
    """Corrección por refracción atmosférica (grados) según el modelo de NOAA.

    Función del ángulo de elevación geométrico. Aproximación válida para
    condiciones estándar (10 °C, 101.325 kPa). Devuelve un valor positivo que se
    **suma** a la elevación geométrica para obtener la aparente.
    """
    elev = np.asarray(elevation_deg, dtype=float)
    er = np.radians(elev)
    tan_er = np.tan(er)

    # Cuatro regímenes según la altura sobre el horizonte (resultado en arcosegundos).
    high = 0.0  # > 85°: refracción despreciable.
    mid = (58.1 / tan_er - 0.07 / tan_er**3 + 0.000086 / tan_er**5)  # 5°–85°
    low = (1735.0 + elev * (-518.2 + elev * (103.4 + elev * (-12.79 + elev * 0.711))))  # -0.575°–5°
    very_low = -20.774 / tan_er  # < -0.575°

    arcsec = np.select(
        [elev > 85.0, elev > 5.0, elev > -0.575],
        [high, mid, low],
        default=very_low,
    )
    return arcsec / 3600.0
