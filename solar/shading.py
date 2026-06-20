"""Geometría de sombreado para protecciones solares de ventanas (numpy puro).

Ángulos de sombra relativos a una ventana vertical orientada según el azimut de su
pared (``wall_az``, dirección hacia la que mira, convención N=0°):

- **HSA** (horizontal shadow angle) γ = azimut_solar − azimut_pared, envuelto a [−180, 180].
  El Sol ilumina la ventana cuando |γ| < 90°.
- **VSA** (vertical shadow angle / *profile angle*): altura solar proyectada en el plano
  perpendicular a la ventana. ``tan(VSA) = tan(altura) / cos(γ)``.

**Alero horizontal** de profundidad ``depth`` (saliente desde la pared), montado a una
distancia vertical ``height`` por encima del antepecho (parte baja) de la ventana de altura
``window_h``. La fracción de la altura de la ventana en sombra es:

    f = clip( (depth·tan(VSA) − offset) / window_h , 0, 1)

donde ``offset`` = distancia del alero por encima del dintel (parte alta). La ventana queda
**completamente** sombreada cuando VSA ≥ ``arctan((window_h + offset) / depth)``.

Referencias: Olgyay; Szokolay, *Introduction to Architectural Science*.
"""

from __future__ import annotations

import numpy as np


def wall_solar_azimuth(solar_azimuth, wall_azimuth) -> np.ndarray:
    """HSA γ en [−180, 180]: ángulo horizontal entre el Sol y la normal a la ventana."""
    g = (np.asarray(solar_azimuth, dtype=float) - wall_azimuth + 180.0) % 360.0 - 180.0
    return g


def illuminated(solar_azimuth, solar_elevation, wall_azimuth) -> np.ndarray:
    """True donde el Sol incide sobre la cara de la ventana (sobre horizonte y |γ| < 90°)."""
    g = wall_solar_azimuth(solar_azimuth, wall_azimuth)
    return (np.asarray(solar_elevation, dtype=float) > 0.0) & (np.abs(g) < 90.0)


def vertical_shadow_angle(solar_azimuth, solar_elevation, wall_azimuth) -> np.ndarray:
    """VSA (profile angle) en grados. NaN donde el Sol no ilumina la ventana."""
    g = wall_solar_azimuth(solar_azimuth, wall_azimuth)
    elev = np.asarray(solar_elevation, dtype=float)
    cos_g = np.cos(np.radians(g))
    ok = (elev > 0.0) & (np.abs(g) < 90.0)
    vsa = np.full(np.shape(elev), np.nan, dtype=float)
    vsa[ok] = np.degrees(np.arctan(np.tan(np.radians(elev[ok])) / cos_g[ok]))
    return vsa


def overhang_full_shade_vsa(depth: float, window_h: float, offset: float = 0.0) -> float:
    """VSA de corte: por encima de este ángulo la ventana queda completamente en sombra."""
    if depth <= 0:
        return 90.0
    return float(np.degrees(np.arctan((window_h + offset) / depth)))


def overhang_shaded_fraction(solar_azimuth, solar_elevation, wall_azimuth,
                             depth: float, window_h: float, offset: float = 0.0) -> np.ndarray:
    """Fracción [0, 1] de la altura de la ventana sombreada por un alero horizontal."""
    vsa = vertical_shadow_angle(solar_azimuth, solar_elevation, wall_azimuth)
    drop = depth * np.tan(np.radians(vsa))  # cuánto baja la sombra desde el alero
    frac = (drop - offset) / window_h
    frac = np.clip(frac, 0.0, 1.0)
    return np.where(np.isnan(vsa), 0.0, frac)


def overhang_mask_curve(wall_azimuth, depth: float, window_h: float, offset: float = 0.0,
                        n: int = 181):
    """Curva límite (azimut, elevación) de sombra COMPLETA de un alero de **ancho infinito**.

    Caso idealizado (sin desplazamiento lateral): por encima de esta curva la ventana queda
    totalmente sombreada. Para un alero de ancho finito úsese ``shaded_fraction``.
    """
    cutoff = overhang_full_shade_vsa(depth, window_h, offset)
    g = np.linspace(-89.9, 89.9, n)  # HSA dentro de la cara iluminada
    elev = np.degrees(np.arctan(np.tan(np.radians(cutoff)) * np.cos(np.radians(g))))
    azimuth = (wall_azimuth + g) % 360.0
    return azimuth, elev


def lateral_cutoff_hsa(ext: float, depth: float) -> float:
    """HSA de corte lateral del alero: ``arctan(extensión / profundidad)`` (grados).

    Para |γ| mayor que este ángulo (Sol más de costado), la sombra del alero se desplaza más
    que la extensión y el borde de la ventana empieza a recibir sol. Con ``ext = 0`` el corte
    es 0° (un alero del ancho exacto de la ventana sólo la sombrea del todo de frente).
    """
    if depth <= 0:
        return 0.0
    return float(np.degrees(np.arctan(ext / depth)))


def shaded_fraction(sun_azimuth, sun_elevation, wall_azimuth, depth: float,
                    window_w: float, window_h: float, offset: float = 0.0,
                    ext_left: float = 0.0, ext_right: float = 0.0, ny: int = 31):
    """Fracción [0,1] del **área** de la ventana sombreada por un alero horizontal de ancho
    finito, proyectando correctamente su geometría (con desplazamiento lateral).

    El alero abarca lateralmente desde ``-ext_left`` hasta ``window_w + ext_right`` (extensión
    independiente a cada lado) y sale ``depth`` desde la pared, a una altura ``window_h +
    offset`` sobre el antepecho.

    Vectorizado: acepta escalares o arrays de posiciones solares (de cualquier forma).
    """
    az = np.asarray(sun_azimuth, dtype=float)
    el = np.asarray(sun_elevation, dtype=float)
    g = wall_solar_azimuth(az, wall_azimuth)
    lit = (el > 0.0) & (np.abs(g) < 89.999)

    with np.errstate(invalid="ignore", divide="ignore"):
        tan_vsa = np.tan(np.radians(el)) / np.cos(np.radians(g))  # = tan(α)/cos(γ)
        tan_g = np.tan(np.radians(g))

    # Muestreo en altura de la ventana: para cada y, ¿qué tramo en x queda bloqueado?
    y = np.linspace(0.0, window_h, ny)
    with np.errstate(invalid="ignore", divide="ignore"):
        oc = (window_h + offset - y) / tan_vsa[..., None]   # distancia (perpendicular) del cruce
        shift = oc * tan_g[..., None]                       # desplazamiento lateral de la sombra
    under = (oc >= 0.0) & (oc <= depth)                     # el rayo pasa bajo el alero
    lo = np.maximum(0.0, -ext_left - shift)
    hi = np.minimum(window_w, window_w + ext_right - shift)
    blocked_len = np.where(under, np.clip(hi - lo, 0.0, window_w), 0.0)

    frac = blocked_len.mean(axis=-1) / window_w
    frac = np.where(lit, frac, 0.0)
    return float(frac) if np.ndim(az) == 0 else frac


def window_shade_grid(wall_azimuth, depth: float, window_w: float, window_h: float,
                      offset: float, ext_left: float, ext_right: float,
                      sun_azimuth: float, sun_elevation: float, nx: int = 140, ny: int = 140):
    """Malla booleana (ny, nx) de los puntos de la ventana en sombra, para el alzado.

    Alero horizontal con extensión lateral independiente a cada lado (``ext_left``,
    ``ext_right``). Devuelve ``(X, Y, blocked)`` en metros (x a lo ancho, y en altura).
    """
    X = np.linspace(0.0, window_w, nx)
    Y = np.linspace(0.0, window_h, ny)
    XX, YY = np.meshgrid(X, Y)
    if not illuminated(sun_azimuth, sun_elevation, wall_azimuth):
        return XX, YY, np.zeros_like(XX, dtype=bool)
    g = float(wall_solar_azimuth(sun_azimuth, wall_azimuth))
    tan_vsa = np.tan(np.radians(sun_elevation)) / np.cos(np.radians(g))
    oc = (window_h + offset - YY) / tan_vsa
    shift = oc * np.tan(np.radians(g))
    blocked = (oc >= 0.0) & (oc <= depth) & (XX + shift >= -ext_left) & (XX + shift <= window_w + ext_right)
    return XX, YY, blocked
