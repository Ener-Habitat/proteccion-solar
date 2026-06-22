# Pruebas (tests)

La suite valida el **núcleo de cálculo** (no la UI): posición solar, geometría de la carta y
geometría de sombreado. Se ejecuta con:

```bash
uv run pytest           # toda la suite
uv run pytest -q        # resumen compacto
uv run pytest tests/test_shading.py -q   # un archivo
```

Estado actual: **64 pruebas pasan, 1 se omite** (Tromsø en invierno: el Sol no sale, caso sin
trayectoria). `pvlib`/`pandas` son dependencias **solo de desarrollo** (validación); la app
desplegada usa únicamente `numpy`/`matplotlib`.

---

## `tests/test_position.py` — núcleo solar validado contra pvlib

Compara la posición solar propia (NOAA/Meeus, numpy puro) contra el **SPA de `pvlib`** en
6 ubicaciones (Temixco, Mérida, CDMX, Quito, Tromsø, Sydney) y 4 fechas (solsticios y
equinoccios de 2026).

| Prueba | Qué verifica |
|---|---|
| `test_elevation_and_azimuth_match_pvlib` | Elevación con error < 0.2° y azimut < 0.3° vs pvlib, todo el día (Sol > 3°), en cada sitio y fecha (parametrizada). |
| `test_declination_and_eot_match_pvlib` | Declinación con error < 0.5° vs una aproximación independiente, todo el año. |
| `test_physical_sanity_summer_tropic_azimuth_north` | En Mérida (21°N) al mediodía del solsticio de verano el Sol está al Norte (azimut ≈ 0°) y muy alto (> 85°) — el punto subsolar (23.5°N) queda al norte. |
| `test_scalar_input_returns_array` | Entradas escalares devuelven arrays finitos (API consistente). |

## `tests/test_geometry.py` — geometría de la carta

| Prueba | Qué verifica |
|---|---|
| `test_local_to_utc_offset_from_longitude` | El desfase de hora se deriva de la longitud (hora solar media), sin zona horaria. |
| `test_day_track_only_above_horizon` | La trayectoria diaria devuelve solo puntos sobre el horizonte; azimut en [0, 360]. |
| `test_to_display_azimuth_conventions` | Conversión de convención de azimut N=0° ↔ S=0°. |
| `test_break_wrap_inserts_nan_on_jump` | Se inserta NaN donde el azimut "envuelve" (evita líneas falsas en la carta). |
| `test_day_events_equinox_about_twelve_hours` | En el equinoccio el día dura ≈ 12 h; orto < mediodía solar < ocaso. |
| `test_day_events_polar_night_and_day` | Detecta noche polar (Tromsø dic) y sol de medianoche (Tromsø jun). |
| `test_sun_at_returns_scalars` | La posición en un instante devuelve escalares con elevación válida. |

## `tests/test_shading.py` — geometría de sombreado (alero + aletas)

**Ángulos y geometría básica**

| Prueba | Qué verifica |
|---|---|
| `test_hsa_wrapping` | HSA = azimut − orientación, envuelto a [−180, 180]. |
| `test_illuminated_face` | El Sol ilumina la cara solo si está sobre el horizonte y \|HSA\| < 90°. |
| `test_vsa_equals_elevation_when_facing` | Con el Sol de frente (HSA=0), VSA = elevación; detrás → NaN. |
| `test_overhang_cutoff_geometry` | VSA de corte del alero = `arctan((alto+offset)/profundidad)`. |
| `test_lateral_cutoff_hsa_geometry` | HSA de corte lateral de la extensión = `arctan(extensión/profundidad)`. |
| `test_fin_full_shade_hsa_geometry` | HSA de corte de la aleta = `arctan(ancho/profundidad)`. |
| `test_mask_curve_peaks_at_cutoff` | La curva de máscara del alero alcanza su máximo (VSA de corte) de frente y decae a los lados. |

**Fracción sombreada (ray casting)**

| Prueba | Qué verifica |
|---|---|
| `test_shaded_fraction_bounds` | Sol alto de frente → 100% sombreado; Sol bajo → poco; Sol detrás → 0. |
| `test_finite_overhang_off_axis_shades_less` | Un alero de ancho finito sombrea menos de costado que de frente (entra luz lateral). |
| `test_side_extension_increases_shading` | Extender el alero del lado del Sol aumenta la sombra. |
| `test_extension_is_side_independent` | La extensión de un lado no ayuda con el Sol del lado contrario. |
| `test_vertical_fin_shades_side_sun` | La aleta del lado del Sol aumenta la sombra; la del lado contrario no. |
| `test_vertical_extension_helps_high_side_sun` | La extensión vertical de la aleta cubre el Sol más alto de costado. |
| `test_shaded_fraction_vectorized_and_grid_agree` | La fracción vectorizada concuerda con la malla del alzado (tolerancia de discretización). |

**Física y validaciones (metodología estereográfica)**

| Prueba | Qué verifica |
|---|---|
| `test_physical_summer_shaded_more_than_winter_temperate` | Alero sur en latitud templada (Madrid): sombrea más en verano que en invierno. |
| `test_tropical_south_window_not_lit_at_summer_noon` | En el trópico, a mediodía de verano el Sol está al Norte → una ventana Sur no recibe sol directo (la intuición del alero sur se invierte). |
| `test_raycast_matches_analytic_vsa_arc` | El ray casting recupera el **arco VSA analítico** en el límite de alero ancho (la ventana pasa a 100% sombreada justo en el VSA de corte). |
| `test_constant_vsa_locus_is_a_circle` | El locus de VSA constante, proyectado en estereográfica, es un **círculo exacto** (residual < 1e‑6) — justifica dibujar la máscara como arco suave. |
| `test_adding_device_never_reduces_shade` | **Unión (OR):** añadir aletas o extensiones nunca reduce la fracción sombreada. |

**Borde de sombra 100% — ray casting y forma cerrada** (ver [`docs/metodologia-sombra.md`](docs/metodologia-sombra.md))

| Prueba | Qué verifica |
|---|---|
| `test_exact_fraction_matches_dense_blocked_grid` | `shaded_fraction` (exacto en x) coincide con la malla densa de `_blocked` (400×400) para celosías completas. |
| `test_full_shade_boundary_reduces_to_overhang` | El borde por ray casting sin aletas recupera el arco de VSA constante. |
| `test_full_shade_boundary_is_true_locus_and_smooth` | El borde por ray casting es el locus real (dentro 100%, fuera no) y suave en el centro (sin sierra). |
| `test_analytic_boundary_matches_raycasting` | El borde **en forma cerrada** coincide con el ray casting a < 0.3° (región significativa) en 5 configuraciones. |
| `test_analytic_boundary_is_true_locus` | El borde analítico es el locus real de sombra 100% (validado contra área densa). |
| `test_analytic_boundary_regimes_and_edges` | Regímenes del borde analítico: reducción al alero, alas (corte HSA), salida finita y suave. |
| `test_practical_boundary_smooth_and_below_strict` | El borde **práctico (99% área)** nunca exige más sol que el 100% estricto y es **suave** aun en configs asimétricas que hacen saltar el estricto. |

---

### Notas

- La posición solar propia se valida contra `pvlib` (SPA NREL) con error máximo ~0.014° en
  elevación y ~0.06° en azimut para todo un año (ver `test_position.py`).
- Las pruebas de validación (`test_raycast_matches_analytic_vsa_arc`,
  `test_constant_vsa_locus_is_a_circle`, `test_adding_device_never_reduces_shade`) siguen la
  metodología de cartas estereográficas (Szokolay; Yanda & Jones para alero finito): el ray
  casting es la capa autoritativa y coincide con la máscara analítica en el límite idealizado.
