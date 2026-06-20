"""Renderizado de la carta de trayectoria solar con matplotlib (cartesiana y polar).

La interactividad la dan los inputs reactivos de Shiny (fecha, hora, toggles); aquí sólo
producimos la figura. La proyección polar es el clásico diagrama estereográfico de
trayectoria solar (cenit al centro, horizonte al borde, Norte arriba).
"""

from __future__ import annotations

from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from solar import geometry as geo

# Colores de las curvas principales (solsticios/equinoccios).
_KEY_COLORS = {
    "Equinoccios (≈21 mar / 23 sep)": "#e8833a",
    "Solsticio de verano (≈21 jun)": "#c0392b",
    "Solsticio de invierno (≈21 dic)": "#2e86c1",
}

# Mapa de color cíclico para las curvas mensuales (dic≈ene).
_MONTH_CMAP = matplotlib.colormaps["twilight_shifted"]
_MONTH_NORM = Normalize(vmin=1, vmax=12)


def _month_color(month_index_0based: int):
    return _MONTH_CMAP(_MONTH_NORM(month_index_0based + 1))


def _break_wrap(azimuth: np.ndarray, *others: np.ndarray):
    """Inserta NaN donde el azimut "envuelve" (salto > 180°) para no dibujar líneas falsas."""
    az = np.asarray(azimuth, dtype=float)
    if az.size < 2:
        return (az, *[np.asarray(o, dtype=float) for o in others])
    jumps = np.where(np.abs(np.diff(az)) > 180.0)[0] + 1
    az = np.insert(az, jumps, np.nan)
    out = [np.insert(np.asarray(o, dtype=float), jumps, np.nan) for o in others]
    return (az, *out)


def render_sunpath(
    latitude: float,
    longitude: float,
    tz_name: str,
    *,
    projection: str = "cartesian",
    azimuth_convention: str = "N0",
    curves: str = "monthly",
    show_analemma: bool = True,
    current_dt: datetime | None = None,
    year: int = 2026,
):
    """Construye y devuelve la figura matplotlib de la carta solar."""
    key_curve = curves == "solstices"
    dates = geo.representative_dates(year) if key_curve else geo.monthly_dates(year)

    if projection == "polar":
        fig, ax = plt.subplots(figsize=(7.6, 7.6), subplot_kw={"projection": "polar"})
        _draw_polar(ax, latitude, longitude, tz_name, dates, key_curve, show_analemma, current_dt)
    else:
        fig, ax = plt.subplots(figsize=(9, 6))
        _draw_cartesian(ax, latitude, longitude, tz_name, dates, key_curve,
                        show_analemma, current_dt, azimuth_convention)

    if not key_curve:
        _add_month_colorbar(fig, ax)

    ax.set_title(f"Trayectoria solar  ·  {latitude:.2f}°, {longitude:.2f}°  ·  {tz_name}",
                 fontsize=11)
    fig.tight_layout()
    return fig


def _draw_cartesian(ax, lat, lon, tz, dates, key_curve, show_analemma, current_dt, convention):
    conv = geo.to_display_azimuth
    for i, (label, date) in enumerate(dates.items()):
        t = geo.day_track(date, lat, lon, tz)
        az, elev = _break_wrap(conv(t["azimuth"], convention), t["elevation"])
        if key_curve:
            ax.plot(az, elev, color=_KEY_COLORS.get(label), lw=1.9, label=label)
        else:
            ax.plot(az, elev, color=_month_color(i), lw=1.3)

    if show_analemma:
        for h in range(4, 21):
            a = geo.hour_analemma(h, lat, lon, tz)
            if a["azimuth"].size == 0:
                continue
            az = conv(a["azimuth"], convention)
            ax.plot(az, a["elevation"], ":", color="0.45", lw=0.7)
            i = int(np.argmax(a["elevation"]))
            ax.annotate(f"{h}h", (az[i], a["elevation"][i]), fontsize=6.5,
                        color="0.4", ha="center", va="bottom")

    _plot_current(ax, lat, lon, tz, current_dt, polar=False, convention=convention)

    ax.set_xlim(0, 360)
    ax.set_ylim(0, 90)
    ax.set_xticks(np.arange(0, 361, 45))
    ax.set_xticklabels(_compass_ticklabels(convention))
    ax.set_xlabel("Azimut")
    ax.set_ylabel("Elevación solar (°)")
    ax.grid(True, alpha=0.3)
    if key_curve:
        ax.legend(loc="upper right", fontsize=8)


def _draw_polar(ax, lat, lon, tz, dates, key_curve, show_analemma, current_dt):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)  # azimut horario
    for i, (label, date) in enumerate(dates.items()):
        t = geo.day_track(date, lat, lon, tz)
        theta, r = _break_wrap(t["azimuth"], 90.0 - t["elevation"])  # r = ángulo cenital
        if key_curve:
            ax.plot(np.radians(theta), r, color=_KEY_COLORS.get(label), lw=1.9, label=label)
        else:
            ax.plot(np.radians(theta), r, color=_month_color(i), lw=1.3)

    if show_analemma:
        for h in range(4, 21):
            a = geo.hour_analemma(h, lat, lon, tz)
            if a["azimuth"].size == 0:
                continue
            ax.plot(np.radians(a["azimuth"]), 90.0 - a["elevation"], ":", color="0.45", lw=0.7)

    _plot_current(ax, lat, lon, tz, current_dt, polar=True)

    ax.set_rlim(0, 90)
    ax.set_rgrids([15, 30, 45, 60, 75], labels=["75°", "60°", "45°", "30°", "15°"],
                  angle=22.5, fontsize=7)
    ax.set_thetagrids(np.arange(0, 360, 45),
                      labels=["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    if key_curve:
        ax.legend(loc="lower right", bbox_to_anchor=(1.12, -0.05), fontsize=8)


def _plot_current(ax, lat, lon, tz, current_dt, *, polar, convention="N0"):
    if current_dt is None:
        return
    s = geo.sun_at(current_dt, lat, lon, tz)
    if s["apparent_elevation"] <= 0:
        return
    if polar:
        ax.plot(np.radians(s["azimuth"]), 90.0 - s["apparent_elevation"],
                "o", color="#f1c40f", markersize=13, markeredgecolor="#b9770e", zorder=5)
    else:
        az = float(geo.to_display_azimuth(np.array([s["azimuth"]]), convention)[0])
        ax.plot(az, s["apparent_elevation"], "o", color="#f1c40f",
                markersize=13, markeredgecolor="#b9770e", zorder=5)


def _add_month_colorbar(fig, ax):
    """Barra de color con los 12 meses para las curvas mensuales."""
    sm = ScalarMappable(norm=_MONTH_NORM, cmap=_MONTH_CMAP)
    cbar = fig.colorbar(sm, ax=ax, ticks=range(1, 13), pad=0.08,
                        fraction=0.046, aspect=30)
    cbar.ax.set_yticklabels(geo.MONTH_LABELS, fontsize=7)
    cbar.set_label("Día 21 de cada mes", fontsize=8)


def _compass_ticklabels(convention: str):
    """Etiquetas de brújula para el eje x cartesiano según la convención de azimut."""
    if convention == "S0":  # 0°=S, horario hacia el Oeste
        return ["S", "SW", "W", "NW", "N", "NE", "E", "SE", "S"]
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"]
