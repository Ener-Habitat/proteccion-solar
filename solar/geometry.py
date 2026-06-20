"""Geometría de la carta solar: trayectorias diarias, analema horario y posición actual.

Construye los datos (azimut, elevación) que dibuja ``charts.sunpath`` a partir del núcleo
``solar.position``. Trabaja en **Hora Solar Estándar Local (LST)**: un desfase UTC fijo
(sin horario de verano) derivado de la zona IANA. Esto evita discontinuidades de DST en las
curvas y es la convención habitual en diagramas de trayectoria solar.

Sin pandas: sólo numpy + ``zoneinfo`` de la stdlib (en Pyodide requiere el paquete ``tzdata``).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


def standard_utc_offset(tz_name: str, year: int = 2026) -> timedelta:
    """Desfase UTC de la **hora estándar** (sin DST) de una zona IANA.

    Se calcula como ``utcoffset - dst`` en una fecha de referencia, lo que devuelve
    siempre el desfase base aunque la fecha caiga en horario de verano.
    """
    tz = ZoneInfo(tz_name)
    ref = datetime(year, 1, 1, 12)
    return tz.utcoffset(ref) - tz.dst(ref)


def _local_std_to_utc(local_times_dt64: np.ndarray, offset: timedelta) -> np.ndarray:
    """Convierte tiempos LST (datetime64 naive) a UTC restando el desfase fijo."""
    off = np.timedelta64(int(offset.total_seconds()), "s")
    return (local_times_dt64.astype("datetime64[s]") - off)


def day_track(date_iso: str, latitude: float, longitude: float, tz_name: str,
              step_min: int = 5) -> dict:
    """Trayectoria solar de un día (en LST) en una geolocalización.

    Returns dict con ``azimuth`` y ``elevation`` (sólo puntos sobre el horizonte) y
    ``time_h`` (hora local decimal), listos para graficar.
    """
    offset = standard_utc_offset(tz_name, int(date_iso[:4]))
    start = np.datetime64(f"{date_iso}T00:00", "s")
    steps = np.arange(0, 24 * 60, step_min)
    local = start + steps * np.timedelta64(1, "m")
    utc = _local_std_to_utc(local, offset)

    sp = solar_position(utc, latitude, longitude)
    above = sp["apparent_elevation"] > 0.0
    return {
        "azimuth": sp["azimuth"][above],
        "elevation": sp["apparent_elevation"][above],
        "time_h": steps[above] / 60.0,
    }


def hour_analemma(hour: int, latitude: float, longitude: float, tz_name: str,
                  year: int = 2026, step_days: int = 3) -> dict:
    """Analema: posición del Sol a una misma hora LST a lo largo del año (curva en 8)."""
    offset = standard_utc_offset(tz_name, year)
    start = np.datetime64(f"{year}-01-01T00:00", "s") + np.timedelta64(hour * 60, "m")
    days = np.arange(0, 365, step_days)
    local = start + days * np.timedelta64(1, "D")
    utc = _local_std_to_utc(local, offset)

    sp = solar_position(utc, latitude, longitude)
    above = sp["apparent_elevation"] > 0.0
    return {"azimuth": sp["azimuth"][above], "elevation": sp["apparent_elevation"][above]}


def day_events(date_iso: str, latitude: float, longitude: float, tz_name: str) -> dict:
    """Orto, ocaso, mediodía solar y duración del día (en hora local estándar, LST).

    Se calcula muestreando el día a 1 min y detectando los cruces de la elevación
    aparente por 0°. Maneja correctamente el día y la noche polares (devuelve ``None``).

    Returns dict: ``sunrise``, ``sunset``, ``solar_noon`` (horas locales decimales o None),
    ``day_length`` (horas), ``max_elevation`` (°), ``polar_day``/``polar_night`` (bool).
    """
    offset = standard_utc_offset(tz_name, int(date_iso[:4]))
    start = np.datetime64(f"{date_iso}T00:00", "s")
    minutes = np.arange(0, 24 * 60 + 1)
    local = start + minutes * np.timedelta64(1, "m")
    utc = _local_std_to_utc(local, offset)
    sp = solar_position(utc, latitude, longitude)
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

    # Cruces por cero: signo de elev cambia entre muestras consecutivas.
    crossings = np.where(np.diff(np.sign(elev)))[0]
    rises = [c for c in crossings if elev[c + 1] > elev[c]]
    sets = [c for c in crossings if elev[c + 1] < elev[c]]
    if rises:
        result["sunrise"] = _interp_zero(hours, elev, rises[0])
    if sets:
        result["sunset"] = _interp_zero(hours, elev, sets[-1])
    if result["sunrise"] is not None and result["sunset"] is not None:
        result["day_length"] = result["sunset"] - result["sunrise"]

    # Mediodía solar = instante de máxima elevación.
    result["solar_noon"] = float(hours[int(np.argmax(elev))])
    return result


def _interp_zero(x: np.ndarray, y: np.ndarray, i: int) -> float:
    """Interpola linealmente la abscisa donde y cruza 0 entre los índices i e i+1."""
    x0, x1, y0, y1 = x[i], x[i + 1], y[i], y[i + 1]
    return float(x0 - y0 * (x1 - x0) / (y1 - y0))


def sun_at(local_dt: datetime, latitude: float, longitude: float, tz_name: str) -> dict:
    """Posición y datos solares en un instante de **hora civil local** (con DST si aplica).

    A diferencia de las curvas (que usan LST), el punto "ahora" respeta la hora civil que
    elige el usuario. Devuelve escalares (no arrays).
    """
    aware = local_dt.replace(tzinfo=ZoneInfo(tz_name))
    utc = aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    sp = solar_position(np.datetime64(utc, "s"), latitude, longitude)
    return {k: float(v[0]) for k, v in sp.items()}


def representative_dates(year: int = 2026) -> dict:
    """{etiqueta: fecha_iso} de solsticios y equinoccios para las curvas principales."""
    return {label: f"{year}-{m:02d}-{d:02d}" for label, (m, d) in SOLSTICES_EQUINOXES.items()}


def monthly_dates(year: int = 2026) -> dict:
    """{etiqueta: fecha_iso} del día 21 de cada mes (familia de curvas mensuales)."""
    return {MONTH_LABELS[m - 1]: f"{year}-{m:02d}-21" for m in range(1, 13)}


def to_display_azimuth(azimuth: np.ndarray, convention: str = "N0") -> np.ndarray:
    """Convierte azimut interno (N=0°, horario) a la convención de presentación.

    ``"N0"`` deja N=0°; ``"S0"`` mide desde el Sur (S=0°, horario hacia el Oeste),
    típico en arquitectura solar.
    """
    if convention == "S0":
        return np.mod(np.asarray(azimuth) - 180.0, 360.0)
    return np.asarray(azimuth)
