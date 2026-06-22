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


def fin_full_shade_hsa(fin_depth: float, window_w: float) -> float:
    """HSA de corte de una aleta vertical: ``arctan(ancho / profundidad)`` (grados).

    Es el dual del VSA del alero: para |γ| ≥ este ángulo (Sol suficientemente de costado),
    la aleta de ese lado sombrea toda la ventana en horizontal.
    """
    if fin_depth <= 0:
        return 90.0
    return float(np.degrees(np.arctan(window_w / fin_depth)))


def _blocked(XX, YY, g_deg, tan_vsa, depth, window_w, window_h, offset, ext_left, ext_right,
             fin_left=0.0, fin_right=0.0, ext_top=0.0):
    """¿Está cada punto (XX, YY) de la ventana en sombra? Une el **alero horizontal** y las
    **aletas verticales** (celosía). Broadcasting: ``g_deg``/``tan_vsa`` pueden ser escalares
    o arrays; XX, YY la malla de la ventana.
    """
    tan_g = np.tan(np.radians(g_deg))
    # Alero horizontal: el rayo cruza el plano del alero a distancia oc; bloquea bajo él.
    with np.errstate(invalid="ignore", divide="ignore"):
        oc = (window_h + offset - YY) / tan_vsa
        shift = oc * tan_g
    blk = (oc >= 0.0) & (oc <= depth) & (XX + shift >= -ext_left) & (XX + shift <= window_w + ext_right)

    # Aletas verticales (cada una en un borde): el rayo cruza el plano de la aleta a oc; bloquea
    # si cae dentro de su profundidad y bajo su borde superior (window_h+ext_top). No se extiende
    # hacia abajo: el Sol está sobre el horizonte, así que el rayo asciende y nunca cruza la aleta
    # por debajo del punto de la ventana.
    fin_top, fin_bot = window_h + ext_top, 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        oc_l = np.where(tan_g < 0.0, -XX / tan_g, np.inf)              # aleta izq. (x=0), Sol por la izq.
        oc_r = np.where(tan_g > 0.0, (window_w - XX) / tan_g, np.inf)  # aleta der. (x=W), Sol por la der.
        y_l = YY + oc_l * tan_vsa
        y_r = YY + oc_r * tan_vsa
    if fin_left > 0:
        blk = blk | ((oc_l >= 0.0) & (oc_l <= fin_left) & (y_l >= fin_bot) & (y_l <= fin_top))
    if fin_right > 0:
        blk = blk | ((oc_r >= 0.0) & (oc_r <= fin_right) & (y_r >= fin_bot) & (y_r <= fin_top))
    return blk


def _row_coverage(g_deg, tan_vsa, depth, window_w, window_h, offset,
                  ext_left, ext_right, fin_left, fin_right, ext_top, y):
    """Longitud en x (m) de la fila de la ventana a altura ``y`` que queda en sombra.

    **Exacto en x:** en cada fila la sombra del alero y la de la aleta activa son, a lo más,
    **dos intervalos** con fórmula cerrada; se devuelve la longitud de su unión. ``g_deg`` y
    ``tan_vsa`` pueden ser arrays de posiciones solares e ``y`` un eje (final) de alturas — todo
    por broadcasting. Hipótesis: un solo alero + una sola aleta (la activa según el signo de γ).
    """
    W, H = window_w, window_h
    m = np.tan(np.radians(g_deg))
    t = tan_vsa
    with np.errstate(invalid="ignore", divide="ignore"):
        # --- Alero: intervalo A = [a_lo, a_hi] ---
        s = m * (H + offset - y) / t                       # desplazamiento lateral del rayo
        a_lo = np.clip(-ext_left - s, 0.0, W)
        a_hi = np.clip(W + ext_right - s, 0.0, W)
        oh_active = (y >= (H + offset - depth * t)) & (y <= H + offset)
        a_hi = np.where(oh_active, a_hi, a_lo)             # alero inactivo → intervalo vacío

        # --- Aleta activa: intervalo B (una sola, por signo de m) ---
        cap = (H + ext_top - y) / t                        # alcance vertical de la aleta
        b_lo_r = np.clip(W - m * np.minimum(fin_right, cap), 0.0, W)   # aleta der. (m>0)
        b_hi_l = np.clip(-m * np.minimum(fin_left, cap), 0.0, W)       # aleta izq. (m<0)
    right = (m > 0.0) & (fin_right > 0.0)
    left = (m < 0.0) & (fin_left > 0.0)
    b_lo = np.where(right, b_lo_r, 0.0)
    b_hi = np.where(right, float(W), np.where(left, b_hi_l, 0.0))      # sin aleta → vacío

    len_a = a_hi - a_lo
    len_b = b_hi - b_lo
    inter = np.maximum(0.0, np.minimum(a_hi, b_hi) - np.maximum(a_lo, b_lo))
    return len_a + len_b - inter


def shaded_fraction(sun_azimuth, sun_elevation, wall_azimuth, depth: float,
                    window_w: float, window_h: float, offset: float = 0.0,
                    ext_left: float = 0.0, ext_right: float = 0.0,
                    fin_left: float = 0.0, fin_right: float = 0.0,
                    ext_top: float = 0.0, n: int = 81):
    """Fracción [0,1] del **área** de la ventana sombreada por la celosía (alero + aletas).

    Vectorizado: acepta escalares o arrays de posiciones solares (de cualquier forma). Es
    **exacto en x** (longitud cubierta por fila en forma cerrada) e integra sobre ``n`` filas en
    altura por regla trapezoidal (convergencia rápida; error ~0.005 a n=81).
    """
    az = np.asarray(sun_azimuth, dtype=float)
    el = np.asarray(sun_elevation, dtype=float)
    g = wall_solar_azimuth(az, wall_azimuth)
    lit = (el > 0.0) & (np.abs(g) < 89.999)
    with np.errstate(invalid="ignore", divide="ignore"):
        tan_vsa = np.tan(np.radians(el)) / np.cos(np.radians(g))

    Y = np.linspace(0.0, window_h, n)
    cov = _row_coverage(g[..., None], tan_vsa[..., None], depth, window_w, window_h, offset,
                        ext_left, ext_right, fin_left, fin_right, ext_top, Y)
    # Cobertura por fila lineal a trozos → media trapezoidal en y (converge rápido en malla
    # uniforme; sin np.trapz por compatibilidad de versiones de numpy/Pyodide).
    mean_cov = (cov.sum(axis=-1) - 0.5 * (cov[..., 0] + cov[..., -1])) / (n - 1)
    frac = mean_cov / window_w
    frac = np.where(lit, frac, 0.0)
    return float(frac) if np.ndim(az) == 0 else frac


def window_shade_grid(wall_azimuth, depth: float, window_w: float, window_h: float,
                      offset: float, ext_left: float, ext_right: float,
                      sun_azimuth: float, sun_elevation: float,
                      fin_left: float = 0.0, fin_right: float = 0.0,
                      ext_top: float = 0.0, nx: int = 140, ny: int = 140):
    """Malla booleana (ny, nx) de los puntos de la ventana en sombra, para el alzado.

    Celosía: alero horizontal (``ext_left/right``) + aletas verticales (``fin_left/right`` con
    extensión superior ``ext_top``). Devuelve ``(X, Y, blocked)`` en metros.
    """
    X = np.linspace(0.0, window_w, nx)
    Y = np.linspace(0.0, window_h, ny)
    XX, YY = np.meshgrid(X, Y)
    if not illuminated(sun_azimuth, sun_elevation, wall_azimuth):
        return XX, YY, np.zeros_like(XX, dtype=bool)
    g = float(wall_solar_azimuth(sun_azimuth, wall_azimuth))
    tan_vsa = np.tan(np.radians(sun_elevation)) / np.cos(np.radians(g))
    blocked = _blocked(XX, YY, g, tan_vsa, depth, window_w, window_h, offset, ext_left, ext_right,
                       fin_left, fin_right, ext_top)
    return XX, YY, blocked


def full_shade_boundary(wall_azimuth, depth: float, window_w: float, window_h: float,
                        offset: float = 0.0, ext_left: float = 0.0, ext_right: float = 0.0,
                        fin_left: float = 0.0, fin_right: float = 0.0, ext_top: float = 0.0,
                        n_gamma: int = 180, ny: int = 200, _iters: int = 40):
    """Curva del **borde de sombra total (100%)** sobre la estereográfica.

    Devuelve ``(gamma_deg, elev_deg)`` (ambos shape ``(n_gamma,)``): para cada HSA γ, la
    **elevación mínima** a partir de la cual la ventana queda completamente sombreada. La región
    sombreada es ``elev ≥ elev_deg`` (alto en el cielo → cerca del cenit en la carta). Donde
    nunca se alcanza el 100% (p. ej. sin alero, aleta somera) devuelve ``90`` (abierto).

    Sin aletas: forma **cerrada exacta** (arco de VSA constante recortado por el corte lateral
    HSA de la extensión). Con aletas: umbral por γ resuelto por bisección sobre la cobertura
    exacta por fila (:func:`_row_coverage`) → curva continua y suave (sin ``contourf`` ni
    suavizado).
    """
    g = np.linspace(-89.9, 89.9, n_gamma)
    has_fins = fin_left > 0.0 or fin_right > 0.0

    if not has_fins:                                  # --- ruta cerrada exacta ---
        gr = np.radians(g)
        top = window_h + offset
        if depth > 0:
            vsa_cut = overhang_full_shade_vsa(depth, window_h, offset)
            elev_vert = np.degrees(np.arctan(np.tan(np.radians(vsa_cut)) * np.cos(gr)))
        else:
            elev_vert = np.full_like(g, 90.0)
        ext_side = np.where(g >= 0.0, ext_right, ext_left)
        num = top * np.abs(np.sin(gr))
        with np.errstate(divide="ignore", invalid="ignore"):
            elev_lat = np.degrees(np.arctan(num / ext_side))
        elev_lat = np.where(num < 1e-9, 0.0, elev_lat)
        elev_lat = np.where((ext_side <= 1e-9) & (num >= 1e-9), 90.0, elev_lat)
        elev = np.clip(np.maximum(elev_vert, elev_lat), 0.0, 90.0)
        return g, elev

    # --- celosía: bisección por γ del umbral de elevación de sombra 100% ---
    Y = np.linspace(0.0, window_h, ny)
    gcol = g[:, None]
    cosg = np.cos(np.radians(g))

    def is_full(elev):                                # elev (n_gamma,) → bool (n_gamma,)
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.tan(np.radians(elev)) / cosg
        cov = _row_coverage(gcol, t[:, None], depth, window_w, window_h, offset,
                            ext_left, ext_right, fin_left, fin_right, ext_top, Y)
        return cov.min(axis=-1) >= window_w * (1.0 - 1e-6)

    lo = np.full(n_gamma, 0.5)
    hi = np.full(n_gamma, 89.9)
    reachable = is_full(hi.copy())                    # ¿llega a 100% cerca del cenit?
    for _ in range(_iters):
        mid = 0.5 * (lo + hi)
        full = is_full(mid)
        hi = np.where(full, mid, hi)
        lo = np.where(full, lo, mid)
    elev = np.where(reachable, hi, 90.0)
    return g, elev
