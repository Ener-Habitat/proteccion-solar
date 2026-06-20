"""Geometría de la carta solar: trayectorias diarias, analema horario y posición actual.

Construye los datos (azimut, elevación) que dibuja ``charts.sunpath`` a partir del núcleo
``solar.position``. El tiempo se maneja como **hora solar media local**: el desfase respecto
a UTC se deriva de la **longitud** (offset = longitud / 15 h), sin necesidad de una zona
horaria civil. Así el mediodía del reloj cae cerca del mediodía solar y no hace falta
``zoneinfo``/``tzdata``.

Sólo numpy + librería estándar.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from .position import solar_position

# Días representativos del año (mes, día) para las curvas de la carta.
SOLSTICES_EQUINOXES = {
    "Equinoccios (≈21 mar / 23 sep)": (3, 20),
    "Solsticio de verano (≈21 jun)": (6, 21),
    "Solsticio de invierno (≈21 dic)": (12, 21),
}

# Etiquetas cortas de meses para las curvas mensuales (día 21 de cada mes).
MONTH_LABELS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _local_to_utc(local_times_dt64: np.ndarray, longitude: float) -> np.ndarray:
    """Convierte hora solar media local (datetime64) a UTC según la longitud.

    Desfase = longitud/15 horas (Este positivo). UTC = local − desfase.
    """
    off_s = int(round(longitude / 15.0 * 3600.0))
    return local_times_dt64.astype("datetime64[s]") - np.timedelta64(off_s, "s")


def day_track(date_iso: str, latitude: float, longitude: float, step_min: int = 5) -> dict:
    """Trayectoria solar de un día en una geolocalización (hora solar media local).

    Returns dict con ``azimuth`` y ``elevation`` (sólo puntos sobre el horizonte) y
    ``time_h`` (hora local decimal).
    """
    start = np.datetime64(f"{date_iso}T00:00", "s")
    steps = np.arange(0, 24 * 60, step_min)
    local = start + steps * np.timedelta64(1, "m")
    sp = solar_position(_local_to_utc(local, longitude), latitude, longitude)
    above = sp["apparent_elevation"] > 0.0
    return {
        "azimuth": sp["azimuth"][above],
        "elevation": sp["apparent_elevation"][above],
        "time_h": steps[above] / 60.0,
    }


def hour_analemma(hour: int, latitude: float, longitude: float,
                  year: int = 2026, step_days: int = 3) -> dict:
    """Analema: posición del Sol a una misma hora local a lo largo del año (curva en 8)."""
    start = np.datetime64(f"{year}-01-01T00:00", "s") + np.timedelta64(hour * 60, "m")
    days = np.arange(0, 365, step_days)
    local = start + days * np.timedelta64(1, "D")
    sp = solar_position(_local_to_utc(local, longitude), latitude, longitude)
    above = sp["apparent_elevation"] > 0.0
    return {"azimuth": sp["azimuth"][above], "elevation": sp["apparent_elevation"][above]}


def day_events(date_iso: str, latitude: float, longitude: float) -> dict:
    """Orto, ocaso, mediodía solar y duración del día (hora solar media local).

    Maneja correctamente el día y la noche polares. Returns dict: ``sunrise``, ``sunset``,
    ``solar_noon`` (horas decimales o None), ``day_length`` (h), ``max_elevation`` (°),
    ``polar_day``/``polar_night`` (bool).
    """
    start = np.datetime64(f"{date_iso}T00:00", "s")
    minutes = np.arange(0, 24 * 60 + 1)
    local = start + minutes * np.timedelta64(1, "m")
    sp = solar_position(_local_to_utc(local, longitude), latitude, longitude)
    elev = sp["apparent_elevation"]
    hours = minutes / 60.0

    above = elev > 0.0
    result = {
        "sunrise": None, "sunset": None, "solar_noon": None, "day_length": 0.0,
        "max_elevation": float(elev.max()), "polar_day": False, "polar_night": False,
    }
    if above.all():
        result["polar_day"] = True
        result["day_length"] = 24.0
    elif not above.any():
        result["polar_night"] = True
        return result

    crossings = np.where(np.diff(np.sign(elev)))[0]
    rises = [c for c in crossings if elev[c + 1] > elev[c]]
    sets = [c for c in crossings if elev[c + 1] < elev[c]]
    if rises:
        result["sunrise"] = _interp_zero(hours, elev, rises[0])
    if sets:
        result["sunset"] = _interp_zero(hours, elev, sets[-1])
    if result["sunrise"] is not None and result["sunset"] is not None:
        result["day_length"] = result["sunset"] - result["sunrise"]
    result["solar_noon"] = float(hours[int(np.argmax(elev))])
    return result


def _interp_zero(x: np.ndarray, y: np.ndarray, i: int) -> float:
    """Interpola linealmente la abscisa donde y cruza 0 entre los índices i e i+1."""
    x0, x1, y0, y1 = x[i], x[i + 1], y[i], y[i + 1]
    return float(x0 - y0 * (x1 - x0) / (y1 - y0))


def day_hour_points(date_iso: str, latitude: float, longitude: float):
    """Posición del Sol a cada hora en punto de un día, sólo sobre el horizonte.

    Returns ``(hours, azimuth, elevation)`` — para marcar las horas sobre la trayectoria.
    """
    hours = np.arange(0, 24)
    local = np.datetime64(f"{date_iso}T00:00", "s") + hours * np.timedelta64(60, "m")
    sp = solar_position(_local_to_utc(local, longitude), latitude, longitude)
    above = sp["apparent_elevation"] > 0.0
    return hours[above], sp["azimuth"][above], sp["apparent_elevation"][above]


def sun_at(local_dt: datetime, latitude: float, longitude: float) -> dict:
    """Posición y datos solares en un instante de hora solar media local. Escalares."""
    local = np.datetime64(local_dt.replace(microsecond=0), "s")
    sp = solar_position(_local_to_utc(local, longitude), latitude, longitude)
    return {k: float(v[0]) for k, v in sp.items()}


def representative_dates(year: int = 2026) -> dict:
    """{etiqueta: fecha_iso} de solsticios y equinoccios para las curvas principales."""
    return {label: f"{year}-{m:02d}-{d:02d}" for label, (m, d) in SOLSTICES_EQUINOXES.items()}


def monthly_dates(year: int = 2026) -> dict:
    """{etiqueta: fecha_iso} del día 21 de cada mes (familia de curvas mensuales)."""
    return {MONTH_LABELS[m - 1]: f"{year}-{m:02d}-21" for m in range(1, 13)}


def to_display_azimuth(azimuth: np.ndarray, convention: str = "N0") -> np.ndarray:
    """Convierte azimut interno (N=0°, horario) a la convención de presentación."""
    if convention == "S0":
        return np.mod(np.asarray(azimuth) - 180.0, 360.0)
    return np.asarray(azimuth)
