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
    shade_method: str = "practico",
    shade_coverage: float = 0.999999,
    show_protractor: bool = False,
    decompose: bool = False,
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

    if show_protractor and shading:
        _protractor(ax, shading["wall_az"], th)
    if shading:
        if decompose:
            _mask_decomposition(ax, shading, shade_method, shade_coverage)
        else:
            _overhang_mask(ax, shading, shade_method, shade_coverage)
    if shading and (show_protractor or decompose):
        ax.legend(loc="lower left", fontsize=6, framealpha=0.85)

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


_VSA_GRID = "#3f8fb0"   # arcos de VSA (aleros horizontales)
_HSA_GRID = "#c0712e"   # rectas de HSA (aletas verticales)


def _protractor(ax, wall_az, th):
    """Retícula tipo transportador de Olgyay (capa de referencia, tenue): **arcos de VSA
    constante** cada 10° para **aleros horizontales** y **rectas radiales de HSA constante** cada
    15° para **aletas verticales**, relativos a la normal de la ventana ``wall_az``. Sirve para
    leer VSA/HSA y ver que el borde de sombra se compone de estos arcos y rectas."""
    g = np.linspace(-89.9, 89.9, 181)
    for vsa in range(10, 90, 10):                                 # VSA (aleros)
        elev = np.degrees(np.arctan(np.tan(np.radians(vsa)) * np.cos(np.radians(g))))
        ax.plot(np.radians(wall_az + g), _elev_to_r(elev), color=_VSA_GRID, lw=0.5, alpha=0.5, zorder=1)
        ax.annotate(f"{vsa}", (np.radians(wall_az), _elev_to_r(vsa)), fontsize=5.5,
                    color=_VSA_GRID, ha="center", va="center", zorder=1, alpha=0.85)
    for hsa in range(0, 90, 15):                                  # HSA (aletas)
        for sgn in ((1,) if hsa == 0 else (1, -1)):
            thl = np.radians(wall_az + sgn * hsa)
            ax.plot([thl, thl], [0.0, 1.0], color=_HSA_GRID, lw=0.5, ls=(0, (4, 3)), alpha=0.5, zorder=1)
    ax.plot([], [], color=_VSA_GRID, lw=1.0, label="VSA — aleros")
    ax.plot([], [], color=_HSA_GRID, lw=1.0, ls=(0, (4, 3)), label="HSA — aletas")


_DECOMP = (("#e07b39", "alero solo"), ("#2ca02c", "alero + aletas"))


def _mask_decomposition(ax, s, method="practico", coverage=0.999999):
    """Descompone la región de sombra 100% por **procedencia**, derivada de las MISMAS curvas que
    la máscara seleccionada — su **borde exterior coincide** con ella. Dos capas: **alero solo**
    (casquete = borde del método con aletas=0) y **alero + aletas** (el resto de la región
    combinada: lo que las aletas añaden al alero)."""
    wall_az = s["wall_az"]
    depth, ww, wh = s["depth"], s["window_w"], s["window_h"]
    offset = s.get("offset", 0.0)
    ext_l, ext_r = s.get("ext_left", 0.0), s.get("ext_right", 0.0)
    fin_l, fin_r = s.get("fin_left", 0.0), s.get("fin_right", 0.0)
    ext_t = s.get("ext_top", 0.0)
    if method == "raycast":
        boundary = shd.full_shade_boundary
    elif method == "analitico":
        boundary = shd.full_shade_boundary_analytic
    else:
        boundary = shd.practical_shade_boundary
    kw = {"coverage": coverage} if boundary is shd.practical_shade_boundary else {}

    g, e_comb = boundary(wall_az, depth, ww, wh, offset, ext_l, ext_r, fin_l, fin_r, ext_t, **kw)
    _, e_oh = boundary(wall_az, depth, ww, wh, offset, ext_l, ext_r, 0.0, 0.0, ext_t, **kw)   # alero solo
    theta = np.radians(wall_az + g)
    has = e_comb < 89.5
    r_comb = np.where(has, _elev_to_r(e_comb), 0.0)
    r_oh = np.where(e_oh < 89.5, np.minimum(_elev_to_r(e_oh), r_comb), 0.0)

    ax.fill_between(theta, 0.0, r_comb, color="#2ca02c", alpha=0.30, zorder=0)        # alero+aletas (base)
    ax.fill_between(theta, 0.0, r_oh, color="#e07b39", alpha=0.40, zorder=0)          # alero solo (casquete)
    ax.plot(theta, np.where(has, r_comb, np.nan), color="#1696a8", lw=1.0, zorder=1)  # borde = máscara seleccionada
    for col, lab in _DECOMP:
        ax.plot([], [], color=col, lw=6, alpha=0.5, label=lab)
    _mark_device_angles(ax, wall_az, depth, ww, wh, offset, ext_l, ext_r, fin_l, fin_r)


def _overhang_mask(ax, s, method="practico", coverage=0.999999):
    """Máscara de **sombra** de la celosía sobre la estereográfica.

    Dibuja, como curva suave, la región de posiciones solares para las que la ventana queda
    sombreada según ``method``:

    - ``"practico"`` — borde de **cobertura de área** (:func:`shading.practical_shade_boundary`,
      por defecto 99.9999 %): prácticamente el 100 % pero suave (sin saltos por franjas diminutas,
      salvo en asimetrías reales); el más útil para diseño.
    - ``"analitico"`` — **100 % estricto** en forma cerrada (:func:`shading.full_shade_boundary_analytic`).
    - ``"raycast"`` — **100 % estricto** por ray casting (:func:`shading.full_shade_boundary`).

    Anota el VSA del alero y los HSA laterales (extensión o aleta).
    """
    wall_az = s["wall_az"]
    depth, ww, wh = s["depth"], s["window_w"], s["window_h"]
    offset = s.get("offset", 0.0)
    ext_l, ext_r = s.get("ext_left", 0.0), s.get("ext_right", 0.0)
    fin_l, fin_r = s.get("fin_left", 0.0), s.get("fin_right", 0.0)
    if method == "raycast":
        boundary = shd.full_shade_boundary
    elif method == "analitico":
        boundary = shd.full_shade_boundary_analytic
    else:
        boundary = shd.practical_shade_boundary

    kw = {"coverage": coverage} if boundary is shd.practical_shade_boundary else {}
    if depth > 0 or fin_l > 0 or fin_r > 0:
        g, elev_full = boundary(wall_az, depth, ww, wh, offset,
                                ext_l, ext_r, fin_l, fin_r, s.get("ext_top", 0.0), **kw)
        if elev_full.min() < 89.5:                       # hay alguna región de sombra total
            theta, r = np.radians(wall_az + g), _elev_to_r(elev_full)
            ax.fill_between(theta, 0.0, r, color=_SHADE_COLOR, alpha=0.20, zorder=0)
            ax.plot(theta, np.where(elev_full >= 89.5, np.nan, r),
                    color="#1696a8", lw=1.0, zorder=1)

    _mark_device_angles(ax, wall_az, depth, ww, wh, offset, ext_l, ext_r, fin_l, fin_r)


def _hsa_line(ax, wall_az, sign, hsa, label):
    th = np.radians(wall_az + sign * hsa)
    ax.plot([th, th], [0.0, 1.0], color="#1696a8", lw=0.9, ls="--", alpha=0.8, zorder=2)
    ax.annotate(label, (th, 0.9), fontsize=6.5, color="#0d7a8a", ha="center", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="#1696a8", lw=0.5, alpha=0.85))


def _mark_device_angles(ax, wall_az, depth, ww, wh, offset, ext_l, ext_r, fin_l=0.0, fin_r=0.0):
    """Marca los ángulos de corte: VSA del alero (profundidad) y, por cada lado, el HSA de la
    aleta (si la hay) o el del alero por su extensión."""
    if depth > 0:
        vsa = shd.overhang_full_shade_vsa(depth, wh, offset)
        ax.annotate(f"VSA {vsa:.0f}°", (np.radians(wall_az), _elev_to_r(vsa)),
                    fontsize=8, color="#0d7a8a", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#1696a8", lw=0.6, alpha=0.85),
                    zorder=6)
    for sign, fin, ext, lbl in ((+1, fin_r, ext_r, "der."), (-1, fin_l, ext_l, "izq.")):
        if fin > 0:                                  # domina la aleta: HSA = arctan(ancho/prof)
            hsa = shd.fin_full_shade_hsa(fin, ww)
            _hsa_line(ax, wall_az, sign, hsa, f"HSA aleta\n{hsa:.0f}° {lbl}")
        elif depth > 0:                              # sólo alero: HSA por su extensión
            hsa = shd.lateral_cutoff_hsa(ext, depth)
            _hsa_line(ax, wall_az, sign, hsa, f"HSA {hsa:.0f}°\n{lbl}")


def _plot_current(ax, lat, lon, current_dt):
    s = geo.sun_at(current_dt, lat, lon)
    if s["apparent_elevation"] <= 0:
        return
    th = np.radians(s["azimuth"])
    r = float(_elev_to_r(s["apparent_elevation"]))
    ax.plot(th, r, "o", color=_SUN_HALO, markersize=18, alpha=0.85, zorder=7)  # halo
    ax.plot(th, r, "o", color=_SUN_FACE, markersize=9, markeredgecolor="#7a0000",
            markeredgewidth=0.8, zorder=8)  # punto rojo
