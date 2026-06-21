"""Carta de trayectoria solar estereográfica (matplotlib).

Diagrama polar estereográfico clásico: cenit al centro, horizonte al borde, Norte arriba,
azimut horario. Dibuja siempre solsticios y equinoccios como referencia, más la trayectoria
del día seleccionado, el analema horario, la posición actual del Sol y —opcionalmente— la
máscara de sombreado de un alero horizontal (Fase 2).

La interactividad la dan los inputs reactivos de Shiny; aquí sólo producimos la figura.
"""

from __future__ import annotations

from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from solar import geometry as geo
from solar import shading as shd

_SHADE_COLOR = "#27c2d6"  # máscara de sombreado del alero

# Colores de las curvas principales (solsticios/equinoccios).
_KEY_COLORS = {
    "Equinoccios (≈21 mar / 23 sep)": "#e8833a",
    "Solsticio de verano (≈21 jun)": "#c0392b",
    "Solsticio de invierno (≈21 dic)": "#2e86c1",
}
_SELECTED_COLOR = "#e10600"   # día seleccionado (rojo)
_SUN_FACE = "#e10600"         # Sol actual (punto rojo con halo)
_SUN_HALO = "#ffd21a"

# Temas: fondo + malla + texto + color de analema/arcos (rojo/cian/amarillo van en ambos).
_THEMES = {
    "claro":   dict(bg="white",   grid="#cfcfcf", text="#333333", analemma="#d98023", ref="#ef9234"),
    "pizarra": dict(bg="#e9eef4", grid="#b9c6d6", text="#2f3e4d", analemma="#cf7a1e", ref="#e07b2a"),
    "oscuro":  dict(bg="#1b2230", grid="#3c4a63", text="#cfd8e3", analemma="#ffb84d", ref="#ff9248"),
}

# Circunferencias de elevación de la malla polar (cada 10°, como en el diagrama clásico).
_ELEV_GRID = [10, 20, 30, 40, 50, 60, 70, 80]
# Días de referencia: 21 de cada mes de jun a dic → 7 arcos de mayor a menor declinación.
_REF_MONTHS = [6, 7, 8, 9, 10, 11, 12]


def _elev_to_r(elev):
    """Proyección estereográfica: radio = tan(ángulo_cenital / 2), normalizado (horizonte=1).

    Conforme (preserva ángulos), como el diagrama de trayectoria solar clásico y el de
    Andrew Marsh. Centro = cenit (elev 90°, r=0); borde = horizonte (elev 0°, r=1).
    """
    zenith = 90.0 - np.asarray(elev, dtype=float)
    return np.tan(np.radians(zenith / 2.0))


def _short_date(iso: str) -> str:
    """'2026-06-21' -> '21 Jun'."""
    y, m, d = iso.split("-")
    return f"{int(d)} {geo.MONTH_LABELS[int(m) - 1]}"


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
    *,
    show_analemma: bool = True,
    current_dt: datetime | None = None,
    mark_sun: bool = True,
    year: int = 2026,
    shading: dict | None = None,
    theme: str = "pizarra",
):
    """Construye y devuelve la figura estereográfica de la carta solar.

    La posición del Sol depende solo de la latitud, la fecha y la hora solar (la longitud no
    influye en la trayectoria aparente). Siempre dibuja solsticios y equinoccios y, además,
    la trayectoria del día seleccionado (``current_dt``) resaltada.

    ``shading`` (opcional): dict con ``wall_az``, ``depth``, ``window_h``, ``offset`` para
    superponer la máscara de sombreado del alero (ángulo de corte VSA proyectado).
    """
    longitude = 0.0  # la longitud se cancela; usamos hora solar media (lon=0)
    selected = current_dt.date().isoformat() if current_dt is not None else None
    th = _THEMES.get(theme, _THEMES["pizarra"])

    fig, ax = plt.subplots(figsize=(7.6, 7.6), subplot_kw={"projection": "polar"})
    fig.patch.set_facecolor(th["bg"])
    ax.set_facecolor(th["bg"])
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)  # azimut horario

    if shading:
        _overhang_mask(ax, shading)

    # Analema horario (líneas de igual hora a lo largo del año), punteado.
    if show_analemma:
        for h in range(4, 21):
            a = geo.hour_analemma(h, latitude, longitude)
            if a["azimuth"].size == 0:
                continue
            ax.plot(np.radians(a["azimuth"]), _elev_to_r(a["elevation"]), ":",
                    color=th["analemma"], lw=0.8, zorder=2)

    # Días de referencia (7 arcos).
    for m in _REF_MONTHS:
        t = geo.day_track(f"{year}-{m:02d}-21", latitude, longitude)
        if t["azimuth"].size == 0:
            continue
        theta, r = _break_wrap(t["azimuth"], _elev_to_r(t["elevation"]))
        ax.plot(np.radians(theta), r, color=th["ref"], lw=1.3, zorder=3)

    # Día seleccionado (rojo) con los marcadores de las horas en punto.
    if selected:
        _selected_day(ax, selected, latitude, longitude)

    if mark_sun and current_dt is not None:
        _plot_current(ax, latitude, longitude, current_dt)

    ax.set_rlim(0, 1.0)
    ax.set_rgrids([float(_elev_to_r(e)) for e in _ELEV_GRID],
                  labels=[f"{e}°" for e in _ELEV_GRID], angle=0, fontsize=6.5)
    ax.set_thetagrids(np.arange(0, 360, 15),
                      labels=["N", "", "", "NE", "", "", "E", "", "", "SE", "", "",
                              "S", "", "", "SW", "", "", "W", "", "", "NW", "", ""])
    for gl in ax.get_xgridlines() + ax.get_ygridlines():
        gl.set_color(th["grid"])
    ax.spines["polar"].set_color(th["grid"])
    ax.tick_params(colors=th["text"])
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(th["text"])
    hemi = "N" if latitude >= 0 else "S"
    ax.set_title(f"Trayectoria solar  ·  latitud {abs(latitude):.2f}° {hemi}",
                 fontsize=11, color=th["text"])
    fig.tight_layout()
    return fig


def _selected_day(ax, date_iso, lat, lon):
    """Dibuja la trayectoria del día seleccionado en rojo con marcadores horarios."""
    t = geo.day_track(date_iso, lat, lon)
    if t["azimuth"].size == 0:
        return
    theta, r = _break_wrap(t["azimuth"], _elev_to_r(t["elevation"]))
    ax.plot(np.radians(theta), r, color=_SELECTED_COLOR, lw=2.2, zorder=4)
    ax.annotate(_short_date(date_iso),
                (np.radians(t["azimuth"][0]), _elev_to_r(t["elevation"][0])),
                fontsize=7, color=_SELECTED_COLOR, ha="center", va="center", zorder=6)

    hh, haz, hel = geo.day_hour_points(date_iso, lat, lon)
    th = np.radians(haz)
    rr = _elev_to_r(hel)
    ax.plot(th, rr, "o", mfc="white", mec=_SELECTED_COLOR, ms=5, mew=1.3, zorder=5)
    for h, t_, r_ in zip(hh, th, rr):
        ax.annotate(f"{h:02d}", (t_, r_), fontsize=6, color=_SELECTED_COLOR,
                    ha="center", va="center", xytext=(0, 7), textcoords="offset points", zorder=6)


def _overhang_mask(ax, s):
    """Máscara de **sombra total real** del alero finito sobre la estereográfica, con los
    ángulos característicos marcados.

    Pinta la región de posiciones solares para las que la ventana queda *completamente*
    sombreada por la geometría finita (alero + extensión lateral). Se corta en los ángulos
    (HSA) donde el costado empieza a recibir sol — a diferencia de la curva VSA idealizada.
    Anota el **VSA** (por la profundidad del alero) y los **HSA laterales** (por las
    extensiones a cada lado).
    """
    wall_az = s["wall_az"]
    depth, ww, wh = s["depth"], s["window_w"], s["window_h"]
    offset = s.get("offset", 0.0)
    ext_l, ext_r = s.get("ext_left", 0.0), s.get("ext_right", 0.0)

    if depth > 0:
        # Frontera analítica de la región de sombra TOTAL: para cada HSA (γ), la elevación
        # mínima α(γ) que cumple a la vez el corte vertical (alero) y el lateral (extensión).
        g = np.linspace(-89.9, 89.9, 181)
        gr = np.radians(g)
        top = wh + offset
        vsa_cut = shd.overhang_full_shade_vsa(depth, wh, offset)
        elev_vert = np.degrees(np.arctan(np.tan(np.radians(vsa_cut)) * np.cos(gr)))

        ext_side = np.where(g >= 0.0, ext_r, ext_l)
        num = top * np.abs(np.sin(gr))                    # desplazamiento lateral en el antepecho
        with np.errstate(divide="ignore", invalid="ignore"):
            elev_lat = np.degrees(np.arctan(num / ext_side))
        elev_lat = np.where(num < 1e-9, 0.0, elev_lat)                          # γ=0: sin desfase
        elev_lat = np.where((ext_side <= 1e-9) & (num >= 1e-9), 90.0, elev_lat)  # sin extensión: no cubre

        elev_min = np.clip(np.maximum(elev_vert, elev_lat), 0.0, 90.0)
        theta = np.radians(wall_az + g)
        r = _elev_to_r(elev_min)
        ax.fill_between(theta, 0.0, r, color=_SHADE_COLOR, alpha=0.20, zorder=0)
        ax.plot(theta, np.where(elev_min >= 89.5, np.nan, r), color="#1696a8", lw=1.0, zorder=1)

    _mark_device_angles(ax, wall_az, depth, ww, wh, offset, ext_l, ext_r)


def _mark_device_angles(ax, wall_az, depth, ww, wh, offset, ext_l, ext_r):
    """Marca en la estereográfica los ángulos de corte del alero: VSA (profundidad) y los
    HSA laterales (extensiones)."""
    if depth <= 0:
        return
    vsa = shd.overhang_full_shade_vsa(depth, wh, offset)
    hsa_l = shd.lateral_cutoff_hsa(ext_l, depth)
    hsa_r = shd.lateral_cutoff_hsa(ext_r, depth)

    # VSA: vértice inferior de la zona (azimut de la pared, elevación = VSA de corte).
    ax.annotate(f"VSA {vsa:.0f}°", (np.radians(wall_az), _elev_to_r(vsa)),
                fontsize=8, color="#0d7a8a", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#1696a8", lw=0.6, alpha=0.85),
                zorder=6)

    # HSA laterales: líneas radiales en azimut_pared ± HSA, con su etiqueta junto al borde.
    for sign, hsa, lbl in ((+1, hsa_r, "der."), (-1, hsa_l, "izq.")):
        th = np.radians(wall_az + sign * hsa)
        ax.plot([th, th], [0.0, 1.0], color="#1696a8", lw=0.9, ls="--", alpha=0.8, zorder=2)
        ax.annotate(f"HSA {hsa:.0f}°\n{lbl}", (th, 0.9), fontsize=6.5, color="#0d7a8a",
                    ha="center", va="center", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="#1696a8", lw=0.5, alpha=0.85))


def _plot_current(ax, lat, lon, current_dt):
    s = geo.sun_at(current_dt, lat, lon)
    if s["apparent_elevation"] <= 0:
        return
    th = np.radians(s["azimuth"])
    r = float(_elev_to_r(s["apparent_elevation"]))
    ax.plot(th, r, "o", color=_SUN_HALO, markersize=18, alpha=0.85, zorder=7)  # halo
    ax.plot(th, r, "o", color=_SUN_FACE, markersize=9, markeredgecolor="#7a0000",
            markeredgewidth=0.8, zorder=8)  # punto rojo
