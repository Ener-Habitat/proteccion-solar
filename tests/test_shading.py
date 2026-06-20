"""Tests de solar.shading (HSA, VSA, alero horizontal)."""

import numpy as np

from solar.geometry import sun_at
from solar.shading import (
    illuminated,
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
    # La malla del alzado promedia a la fracción analítica (tolerancia de discretización).
    _, _, blocked = window_shade_grid(SOUTH, 0.8, 1.2, 1.5, 0.0, 0.0, 0.0, 200.0, 50.0)
    f_scalar = shaded_fraction(200.0, 50.0, SOUTH, 0.8, 1.2, 1.5)
    assert abs(blocked.mean() - f_scalar) < 0.03


def test_tropical_south_window_not_lit_at_summer_noon():
    """En el trópico (Temixco, 18.85°N) a mediodía de verano el Sol está al Norte, así que
    una ventana Sur no recibe sol directo (la intuición del alero sur se invierte)."""
    from datetime import datetime
    s = sun_at(datetime(2026, 6, 21, 12, 30), 18.85, -99.23)
    assert not illuminated(s["azimuth"], s["apparent_elevation"], SOUTH)
