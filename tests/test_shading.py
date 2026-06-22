"""Tests de solar.shading (HSA, VSA, alero horizontal)."""

import numpy as np

from solar.geometry import sun_at
from solar.shading import (
    fin_full_shade_hsa,
    full_shade_boundary,
    full_shade_boundary_analytic,
    illuminated,
    practical_shade_boundary,
    lateral_cutoff_hsa,
    overhang_full_shade_vsa,
    overhang_mask_curve,
    overhang_shaded_fraction,
    shaded_fraction,
    vertical_shadow_angle,
    wall_solar_azimuth,
    window_shade_grid,
)

SOUTH = 180.0  # ventana orientada al Sur (convención N=0°)


def test_hsa_wrapping():
    # Sol al Sur frente a ventana Sur → γ=0; Sol al Este → γ=−90.
    assert wall_solar_azimuth(180.0, SOUTH) == 0.0
    assert wall_solar_azimuth(90.0, SOUTH) == -90.0
    assert wall_solar_azimuth(270.0, SOUTH) == 90.0


def test_illuminated_face():
    # Sol al Sur ilumina ventana Sur; Sol al Norte no.
    assert illuminated(180.0, 30.0, SOUTH)
    assert not illuminated(0.0, 30.0, SOUTH)   # detrás
    assert not illuminated(180.0, -5.0, SOUTH)  # bajo el horizonte


def test_vsa_equals_elevation_when_facing():
    # Sol justo frente a la ventana (γ=0): VSA = altura solar.
    vsa = vertical_shadow_angle(180.0, 45.0, SOUTH)
    assert abs(float(vsa) - 45.0) < 1e-9
    # Sol detrás → NaN.
    assert np.isnan(vertical_shadow_angle(0.0, 45.0, SOUTH))


def test_overhang_cutoff_geometry():
    # depth=1, h=1, offset=0 → cutoff = 45°.
    assert abs(overhang_full_shade_vsa(1.0, 1.0, 0.0) - 45.0) < 1e-9
    # depth=2, h=2 → 45°; depth=1,h=2 → 63.43°.
    assert abs(overhang_full_shade_vsa(1.0, 2.0, 0.0) - np.degrees(np.arctan(2))) < 1e-9


def test_shaded_fraction_bounds():
    # Sol alto frente a ventana → completamente sombreada (1.0).
    f_high = overhang_shaded_fraction(180.0, 80.0, SOUTH, depth=1.0, window_h=1.0)
    assert abs(float(f_high) - 1.0) < 1e-9
    # Sol muy bajo → sin sombra del alero.
    f_low = overhang_shaded_fraction(180.0, 5.0, SOUTH, depth=1.0, window_h=2.0)
    assert float(f_low) < 0.2
    # Sol detrás → 0.
    assert overhang_shaded_fraction(0.0, 45.0, SOUTH, 1.0, 1.0) == 0.0


def test_mask_curve_peaks_at_cutoff():
    az, elev = overhang_mask_curve(SOUTH, depth=1.0, window_h=1.0)
    # En γ=0 (centro, azimut=Sur) la elevación límite = cutoff (45°).
    i = int(np.argmin(np.abs(az - SOUTH)))
    assert abs(elev[i] - 45.0) < 0.1
    # La curva decae hacia los bordes (Sol rasante).
    assert elev[0] < elev[i] and elev[-1] < elev[i]


def test_physical_summer_shaded_more_than_winter_temperate():
    """Alero sobre ventana Sur en latitud templada (Madrid, 40°N): a mediodía sombrea
    más en verano (Sol alto) que en invierno (Sol bajo) — el objetivo bioclimático."""
    from datetime import datetime
    lat, lon = 40.42, -3.70
    s_sum = sun_at(datetime(2026, 6, 21, 12, 0), lat, lon)
    s_win = sun_at(datetime(2026, 12, 21, 12, 0), lat, lon)
    f_sum = overhang_shaded_fraction(s_sum["azimuth"], s_sum["apparent_elevation"], SOUTH, 0.6, 1.5)
    f_win = overhang_shaded_fraction(s_win["azimuth"], s_win["apparent_elevation"], SOUTH, 0.6, 1.5)
    assert float(f_sum) > float(f_win)


def test_finite_overhang_off_axis_shades_less():
    """Con alero de ancho finito (sin extensión lateral), el Sol de costado sombrea MENOS
    que el Sol de frente a la misma altura — entra sol por los lados."""
    on_axis = shaded_fraction(180.0, 50.0, SOUTH, depth=0.8, window_w=1.2, window_h=1.5)
    off_axis = shaded_fraction(180.0 + 55.0, 50.0, SOUTH, depth=0.8, window_w=1.2, window_h=1.5)
    assert on_axis > off_axis
    # Diferencia frente a un alero infinito: éste no distingue el costado.
    inf = float(overhang_shaded_fraction(180.0 + 55.0, 50.0, SOUTH, 0.8, 1.5))
    assert off_axis < inf


def test_side_extension_increases_shading():
    """Extender el alero del lado por el que incide el Sol aumenta la sombra."""
    # Sol a la derecha (γ>0): la sombra se desplaza, expone el borde derecho → extiende der.
    base = shaded_fraction(180.0 + 55.0, 50.0, SOUTH, 0.8, 1.2, 1.5, ext_left=0.0, ext_right=0.0)
    extended = shaded_fraction(180.0 + 55.0, 50.0, SOUTH, 0.8, 1.2, 1.5, ext_left=0.0, ext_right=1.0)
    assert extended > base


def test_extension_is_side_independent():
    """La extensión a un lado no ayuda cuando el Sol incide por el lado contrario."""
    # Para γ>0 importa la extensión derecha; la izquierda no debe cambiar la fracción.
    only_left = shaded_fraction(235.0, 50.0, SOUTH, 0.8, 1.2, 1.5, ext_left=1.0, ext_right=0.0)
    none = shaded_fraction(235.0, 50.0, SOUTH, 0.8, 1.2, 1.5, ext_left=0.0, ext_right=0.0)
    assert abs(only_left - none) < 1e-9


def test_lateral_cutoff_hsa_geometry():
    # ext 0.4, profundidad 0.8 → arctan(0.5) ≈ 26.57°; ext 0 → 0°.
    assert abs(lateral_cutoff_hsa(0.4, 0.8) - np.degrees(np.arctan(0.5))) < 1e-9
    assert lateral_cutoff_hsa(0.0, 0.8) == 0.0


def test_shaded_fraction_vectorized_and_grid_agree():
    # Vectorización sobre arrays.
    az = np.array([180.0, 200.0, 235.0])
    f = shaded_fraction(az, 50.0, SOUTH, 0.8, 1.2, 1.5)
    assert f.shape == (3,)
    # La fracción es exacta en x; concuerda con la malla densa del alzado (solo cuantización
    # de la malla 140×140 del lado de window_shade_grid).
    _, _, blocked = window_shade_grid(SOUTH, 0.8, 1.2, 1.5, 0.0, 0.0, 0.0, 200.0, 50.0)
    f_scalar = shaded_fraction(200.0, 50.0, SOUTH, 0.8, 1.2, 1.5)
    assert abs(blocked.mean() - f_scalar) < 0.01


def test_fin_full_shade_hsa_geometry():
    from solar.shading import fin_full_shade_hsa
    # ancho 1.2, profundidad 0.6 → arctan(2) ≈ 63.43°; sin aleta → 90°.
    assert abs(fin_full_shade_hsa(0.6, 1.2) - np.degrees(np.arctan(2))) < 1e-9
    assert fin_full_shade_hsa(0.0, 1.2) == 90.0


def test_vertical_fin_shades_side_sun():
    """Una aleta del lado por el que incide el Sol aumenta la sombra; la del lado contrario no."""
    base = shaded_fraction(235.0, 45.0, SOUTH, 0.4, 1.2, 1.5)            # γ>0 (Sol a la der.)
    con_der = shaded_fraction(235.0, 45.0, SOUTH, 0.4, 1.2, 1.5, fin_right=0.6)
    con_izq = shaded_fraction(235.0, 45.0, SOUTH, 0.4, 1.2, 1.5, fin_left=0.6)
    assert con_der > base
    assert abs(con_izq - base) < 1e-9    # la aleta izquierda no ayuda con Sol por la derecha


def test_vertical_extension_helps_high_side_sun():
    """La extensión vertical de la aleta cubre el Sol más alto de costado."""
    sin_ext = shaded_fraction(235.0, 68.0, SOUTH, 0.4, 1.2, 1.5, fin_right=0.6)
    con_ext = shaded_fraction(235.0, 68.0, SOUTH, 0.4, 1.2, 1.5, fin_right=0.6, ext_top=0.8)
    assert con_ext >= sin_ext


def test_raycast_matches_analytic_vsa_arc():
    """Validación (reporte): el ray casting (shaded_fraction) recupera el arco VSA analítico
    en el límite de alero ancho. A γ=0 con extensiones grandes, la ventana pasa a 100%
    sombreada justo al cruzar VSA = arctan(H/d)."""
    from solar.shading import overhang_full_shade_vsa
    depth, wh, ww = 0.6, 1.5, 1.2
    vsa_cut = overhang_full_shade_vsa(depth, wh)          # arctan(1.5/0.6) ≈ 68.2°
    f_below = shaded_fraction(SOUTH, vsa_cut - 4, SOUTH, depth, ww, wh, ext_left=3, ext_right=3)
    f_above = shaded_fraction(SOUTH, vsa_cut + 4, SOUTH, depth, ww, wh, ext_left=3, ext_right=3)
    assert f_below < 0.95          # antes del corte: la ventana NO está 100% sombreada
    assert f_above > 0.98          # después del corte: ~100% (recupera el arco)


def test_constant_vsa_locus_is_a_circle():
    """El locus de VSA constante, proyectado en estereográfica, es un círculo (por eso se puede
    dibujar como arco suave). Ajusto un círculo a la curva y el residual debe ser ~0."""
    vsa = np.radians(68.2)
    g = np.radians(np.linspace(-80.0, 80.0, 60))
    elev = np.arctan(np.tan(vsa) * np.cos(g))            # locus VSA constante (rad)
    r = np.tan((np.pi / 2 - elev) / 2)                   # radio estereográfico
    x, y = r * np.sin(g), r * np.cos(g)
    c, *_ = np.linalg.lstsq(np.c_[2 * x, 2 * y, np.ones_like(x)], x**2 + y**2, rcond=None)
    cx, cy = c[0], c[1]
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)           # distancia al centro ajustado
    assert (d.max() - d.min()) < 1e-6                    # equidistante → círculo


def test_adding_device_never_reduces_shade():
    """Unión (OR): añadir aletas o extensiones nunca reduce la fracción sombreada."""
    az = np.array([150.0, 180.0, 210.0, 235.0])
    base = shaded_fraction(az, 45.0, SOUTH, 0.5, 1.2, 1.5)
    with_fins = shaded_fraction(az, 45.0, SOUTH, 0.5, 1.2, 1.5, fin_left=0.5, fin_right=0.5)
    with_ext = shaded_fraction(az, 45.0, SOUTH, 0.5, 1.2, 1.5, ext_left=0.5, ext_right=0.5)
    assert np.all(with_fins >= base - 1e-9)
    assert np.all(with_ext >= base - 1e-9)


def test_tropical_south_window_not_lit_at_summer_noon():
    """En el trópico (Temixco, 18.85°N) a mediodía de verano el Sol está al Norte, así que
    una ventana Sur no recibe sol directo (la intuición del alero sur se invierte)."""
    from datetime import datetime
    s = sun_at(datetime(2026, 6, 21, 12, 30), 18.85, -99.23)
    assert not illuminated(s["azimuth"], s["apparent_elevation"], SOUTH)


# --- Ray casting exacto en x y borde de sombra 100% ---

_CFGS = [
    dict(depth=0.6, ext_right=0.3, fin_right=0.5, ext_top=0.4),
    dict(depth=0.4, offset=0.1, ext_left=0.2, fin_left=0.3, fin_right=0.3, ext_top=0.5),
]


def _frac(az, el, k):
    return shaded_fraction(az, el, SOUTH, k.get("depth", 0.6), 1.2, 1.5, k.get("offset", 0.0),
                           k.get("ext_left", 0.0), k.get("ext_right", 0.0), k.get("fin_left", 0.0),
                           k.get("fin_right", 0.0), k.get("ext_top", 0.0))


def test_exact_fraction_matches_dense_blocked_grid():
    """``shaded_fraction`` (exacto en x) coincide con el kernel ``_blocked`` en malla densa
    400×400, para celosías con alero + extensiones + aletas + offset."""
    worst = 0.0
    for k in _CFGS:
        for az in (185.0, 205.0, 235.0, 150.0):
            for el in (20.0, 45.0, 68.0, 82.0):
                _, _, blk = window_shade_grid(SOUTH, k.get("depth", 0.6), 1.2, 1.5,
                                              k.get("offset", 0.0), k.get("ext_left", 0.0),
                                              k.get("ext_right", 0.0), az, el, k.get("fin_left", 0.0),
                                              k.get("fin_right", 0.0), k.get("ext_top", 0.0),
                                              nx=400, ny=400)
                worst = max(worst, abs(_frac(az, el, k) - blk.mean()))
    assert worst < 0.01


def test_full_shade_boundary_reduces_to_overhang():
    """Sin aletas y con extensiones amplias, el borde 100% recupera el arco de VSA constante
    (el caso solo-alero exacto). Se compara donde el corte vertical domina (|γ| ≤ 60°)."""
    depth, wh = 0.6, 1.5
    g, elev = full_shade_boundary(SOUTH, depth, 1.2, wh, ext_left=3.0, ext_right=3.0)
    vsa = overhang_full_shade_vsa(depth, wh)
    i0 = int(np.argmin(np.abs(g)))
    assert abs(elev[i0] - vsa) < 0.1                       # en γ≈0 el umbral = VSA de corte
    arc = np.degrees(np.arctan(np.tan(np.radians(vsa)) * np.cos(np.radians(g))))
    m = np.abs(g) <= 60.0
    assert np.max(np.abs(elev[m] - arc[m])) < 0.2          # sigue el arco (círculo estereográfico)


def test_full_shade_boundary_is_true_locus_and_smooth():
    """El borde 100% es el locus real (dentro → ~100% sombreada, fuera → no) y es **suave**
    en la región central (sin sierra); las únicas esquinas son los cortes HSA reales (γ ≈ aleta)."""
    k = dict(depth=0.6, fin_left=0.5, fin_right=0.5, ext_top=0.4)
    g, elev = full_shade_boundary(SOUTH, 0.6, 1.2, 1.5, fin_left=0.5, fin_right=0.5, ext_top=0.4)
    # Locus: justo dentro del borde, sombra total; bien afuera, no.
    for gi in (-20.0, 0.0, 25.0):
        i = int(np.argmin(np.abs(g - gi)))
        e0 = elev[i]
        assert _frac(SOUTH + g[i], min(e0 + 2.0, 89.9), k) >= 0.999
        assert _frac(SOUTH + g[i], e0 - 5.0, k) < 0.98
    # Suavidad: segunda diferencia pequeña en la zona central (lejos del corte HSA de la aleta).
    center = np.abs(g) <= 50.0
    assert np.nanmax(np.abs(np.diff(elev[center], 2))) < 1.0


# --- Borde 100% en forma cerrada (metodología analítica) ---

_ANA_CFGS = [
    dict(depth=0.6, ext_left=3.0, ext_right=3.0),                                   # solo alero
    dict(depth=0.6, fin_right=0.5, ext_right=0.3, ext_top=0.4),                     # aleta única
    dict(depth=0.6, fin_left=0.5, fin_right=0.5, ext_top=0.4),                      # celosía simétrica
    dict(depth=0.5, offset=0.2, ext_left=0.2, fin_left=0.3, fin_right=0.5, ext_top=0.3),  # asimétrica
    dict(depth=0.6, fin_left=0.6, fin_right=0.6, ext_top=0.8),                      # ext_top>offset
]


def _boundary_args(k):
    return (SOUTH, k.get("depth", 0.6), 1.2, 1.5, k.get("offset", 0.0),
            k.get("ext_left", 0.0), k.get("ext_right", 0.0),
            k.get("fin_left", 0.0), k.get("fin_right", 0.0), k.get("ext_top", 0.0))


def test_analytic_boundary_matches_raycasting():
    """El borde en forma cerrada coincide con el ray casting (ground truth) en la región
    significativa (excluye el riel 90° y el piso ~horizonte del ala, donde el ray casting topa
    con su bisección y el analítico es de hecho más exacto)."""
    for k in _ANA_CFGS:
        g, e_ray = full_shade_boundary(*_boundary_args(k))
        _, e_ana = full_shade_boundary_analytic(*_boundary_args(k))
        sig = (e_ray < 89.5) & (e_ray > 1.0)
        assert np.max(np.abs(e_ana - e_ray)[sig]) < 0.3


def test_analytic_boundary_is_true_locus():
    """El borde analítico es el locus real de sombra 100%: justo dentro está totalmente
    sombreada; bien afuera, no. (Valida la hipótesis de la arista inferior contra área densa.)"""
    k = dict(depth=0.6, fin_left=0.5, fin_right=0.5, ext_top=0.4)
    g, e = full_shade_boundary_analytic(*_boundary_args(k))
    for gi in (-20.0, 0.0, 25.0):                       # zona central (transición nítida)
        i = int(np.argmin(np.abs(g - gi)))
        e0 = e[i]
        assert _frac(SOUTH + g[i], min(e0 + 2.0, 89.9), k) >= 0.999
        assert _frac(SOUTH + g[i], e0 - 5.0, k) < 0.99


def test_analytic_boundary_regimes_and_edges():
    """Reducción al alero sin aletas; alas (γ≥arctan(W/fin)→sombra total); sin NaN/inf y suave."""
    # Sin aletas: idéntico al borde solo-alero (mismo helper cerrado).
    g, e_ana = full_shade_boundary_analytic(SOUTH, 0.6, 1.2, 1.5, ext_left=0.3, ext_right=0.3)
    _, e_oh = full_shade_boundary(SOUTH, 0.6, 1.2, 1.5, ext_left=0.3, ext_right=0.3)
    assert np.max(np.abs(e_ana - e_oh)) < 0.05
    # Alas: pasado el corte HSA de la aleta, sombra total (elev→0).
    g, e = full_shade_boundary_analytic(SOUTH, 0.6, 1.2, 1.5, fin_left=0.5, fin_right=0.5, ext_top=0.4)
    cut = fin_full_shade_hsa(0.5, 1.2)                  # ≈67.4°
    assert np.all(e[np.abs(g) >= cut + 2.0] < 0.6)
    # Salida finita y suave en el centro (sin NaN/inf, sin sierra).
    assert np.all(np.isfinite(e))
    assert np.nanmax(np.abs(np.diff(e[np.abs(g) <= 50.0], 2))) < 1.0


def test_practical_boundary_smooth_and_below_strict():
    """El borde práctico (99% de área) nunca exige más elevación que el 100% estricto y es
    **suave** incluso en configs asimétricas que hacen *saltar* el estricto (aleta somera +
    extensión del lado opuesto)."""
    args = (SOUTH, 0.6, 1.2, 1.5, 0.0, 0.195, 0.0, 0.0, 0.19, 0.4)
    g, e99 = practical_shade_boundary(*args, coverage=0.99)
    _, e100 = full_shade_boundary_analytic(*args)
    real = e100 > 1.0                                       # excluye las alas (estricto→0, práctico→piso)
    assert np.all(e99[real] <= e100[real] + 1e-6)           # práctico ≤ estricto
    center = np.abs(g) <= 40.0
    assert np.nanmax(np.abs(np.diff(e99[center]))) < 5.0    # sin el salto (~15°) del estricto
    i = int(np.argmin(np.abs(g - 10.0)))                    # donde dibuja, el área es ≥ 99%
    f = shaded_fraction(SOUTH + g[i], e99[i] + 0.5, SOUTH, 0.6, 1.2, 1.5, 0.0, 0.195, 0.0,
                        0.0, 0.19, 0.4)
    assert f >= 0.99


def test_analytic_boundary_hardened_fin_dominant():
    """El borde cerrado toma el MÁXIMO sobre las filas (no solo la inferior): en configs
    dominadas por aletas con ext_top=0 —donde la fila crítica NO es la inferior— ya coincide con
    el ray casting (antes devolvía 'ala'=0 por error)."""
    cfgs = [
        dict(depth=0.6, fin_left=0.5, fin_right=0.5, ext_top=0.0),   # simétrica, ext_top=0
        dict(depth=0.6, fin_left=0.9, fin_right=0.9, ext_top=0.0),   # aletas grandes, ext_top=0
        dict(depth=0.6, fin_right=0.6, ext_left=0.2, ext_top=0.0),   # asimétrica, ext_top=0
    ]
    for k in cfgs:
        g, e_ray = full_shade_boundary(*_boundary_args(k))
        _, e_ana = full_shade_boundary_analytic(*_boundary_args(k))
        sig = (e_ray < 89.5) & (e_ray > 1.0)
        assert np.max(np.abs(e_ana - e_ray)[sig]) < 0.5
