# sun-protections — Diseño

App web interactiva y educativa para visualizar la **trayectoria solar aparente** en una
geolocalización y **diseñar protecciones solares de ventanas** (aleros, parteluces, celosías).

- **Público:** ingeniería / investigación (precisión + algoritmos validados + exportar datos).
- **Stack:** Shiny for Python → `shinylive export` → sitio estático en **GitHub Pages**,
  100% en navegador vía Pyodide/WASM, **sin servidor**. (Verificado por spike, 2026-06-19.)

## Principio de dependencias (decisión: híbrido)

- **Fase 1 (carta solar):** posición solar en **numpy puro** (algoritmo NOAA/Meeus). Sin
  pvlib, sin scipy → carga inicial mucho más ligera y el código es didáctico (se muestran
  las ecuaciones). Deps de runtime: `numpy`, `matplotlib` (+ `tzdata` para zonas horarias).
- **Fase 3 (irradiancia):** se añade `pvlib` (+ `scipy`, `h5py`, `requests`) sólo cuando
  haga falta. Se validará la posición solar propia **contra pvlib** como prueba y como
  recurso educativo (mostrar el error < 0.1°).

`requirements.txt` empieza mínimo y crece por fase. **Gotcha Pyodide:** hay que declarar
TODAS las dependencias (incluido `tzdata`) explícitamente; shinylive no las auto-resuelve.

## Convenciones (importante para investigación)

- **Azimut:** configurable. Default **Norte = 0°, sentido horario** (convención pvlib/NOAA,
  E=90, S=180, W=270). Toggle a **Sur = 0°** (convención frecuente en arquitectura solar).
  Todo cálculo interno usa N=0 y se convierte sólo al presentar.
- **Elevación / altura solar** vs. **ángulo cenital** (z = 90 − elevación): se ofrecen ambos.
- **Tiempo:** entrada en hora local (tz IANA) o solar verdadera; se muestra la
  **ecuación del tiempo** y la corrección de longitud.
- **Elevación aparente:** con corrección por refracción atmosférica (modelo
  Bennett/Saemundsson), distinguida de la geométrica.

## Núcleo solar (numpy puro) — `solar/position.py`

Pipeline NOAA/Meeus (exactitud ~0.01° para 1900–2100):

1. Día juliano (desde fecha/hora UTC) → siglo juliano `T`.
2. Longitud media geométrica `L0`, anomalía media `M`, excentricidad `e`.
3. Ecuación del centro → longitud verdadera → longitud aparente (nutación).
4. Oblicuidad de la eclíptica `ε`.
5. **Declinación** `δ = asin(sin ε · sin λ)`.
6. **Ecuación del tiempo** `E` (minutos).
7. Tiempo solar verdadero → **ángulo horario** `H`.
8. **Elevación** `sin α = sin φ·sin δ + cos φ·cos δ·cos H`.
9. **Azimut** (cuadrante completo).
10. Corrección por **refracción** → elevación aparente.

API vectorizada (acepta escalares o arrays de tiempos):
```python
solar_position(times_utc, lat, lon) -> {
    'apparent_elevation', 'elevation', 'azimuth', 'zenith',
    'declination', 'equation_of_time', 'hour_angle'
}
```

## Estructura de módulos

```
app.py                  # entry: Shiny UI + server (orquesta, no calcula)
solar/
  position.py           # posición solar numpy puro (NOAA). Fase 1
  geometry.py           # transforms carta (cartesiana/polar), analema, líneas hora/fecha
  shading.py            # Fase 2: máscara de sombreado, VSA/HSA, aleros/parteluces/celosía
  irradiance.py         # Fase 3: wrapper pvlib (cielo despejado)
charts/
  sunpath.py            # render carta solar (cartesiana + polar/estereográfica)
  shademask.py          # Fase 2: máscara sobre la carta
data/
  cities.py             # presets de ciudades (lat/lon/tz), p.ej. Temixco/Mérida/CDMX
content/
  edu.py                # textos/ecuaciones del panel educativo (markdown + MathJax)
requirements.txt        # deps por fase (Pyodide)
```
(Verificar que shinylive empaqueta subpaquetes con `__init__.py`; si no, aplanar.)

## Modelo de estado (inputs reactivos)

| Grupo | Inputs |
|---|---|
| Ubicación | lat, lon, tz, preset-ciudad |
| Tiempo | fecha, hora, modo (local/solar), animación on/off |
| Vista | tipo de carta (cartesiana/polar), azimut N0/S0, elevación vs cenital, refracción on/off |
| Ventana (F2) | orientación (azimut pared), ancho, alto, altura antepecho |
| Protección (F2) | tipo (alero/parteluz/celosía), profundidad, posición, ángulo |

## Wireframe (Fase 1)

```
┌───────────────────────────────────────────────────────────────┐
│  Sun-Protections                                   [N0|S0] [↻] │
├──────────────┬────────────────────────────────────────────────┤
│ UBICACIÓN    │   ┌── Carta solar ─────────────────────────┐    │
│ ciudad ▾     │   │  [Cartesiana | Polar]                  │    │
│ lat  20.97   │   │                                        │    │
│ lon -89.62   │   │   curvas: solsticios + equinoccios     │    │
│ tz   ▾       │   │   analema horario (punteado)           │    │
│              │   │   ● posición del sol (fecha/hora)      │    │
│ TIEMPO       │   │   hover → (azimut, elevación)          │    │
│ fecha 📅     │   │                                        │    │
│ hora  ▦──    │   └────────────────────────────────────────┘    │
│ [▶ animar]   │   ┌── Datos ──────┐  ┌── ¿Qué es esto? ───┐    │
│              │   │ δ, E, α, az,  │  │ ecuaciones vivas,  │    │
│ VISTA        │   │ orto/ocaso    │  │ MathJax, enlaces   │    │
│ refracción ☑ │   └───────────────┘  └────────────────────┘    │
└──────────────┴────────────────────────────────────────────────┘
```

## Charting (decisión: matplotlib)

- **matplotlib** (`render.plot`): PNG estático por reactividad. Simple, ligero, ya probado en
  el spike. La interactividad la dan los inputs reactivos (sliders de fecha/hora, toggles,
  animación), no hover/zoom nativos. Sin dependencias extra.
- Posible migración futura a Plotly si se requiere hover/zoom; no es necesario para el MVP.

## Panel educativo (decisión: ecuaciones vivas con MathJax)

- Mostrar las fórmulas clave (declinación `δ`, ecuación del tiempo `E`, elevación `α`,
  azimut) con los **valores actuales sustituidos**, que se recalculan al mover los inputs.
- MathJax desde CDN inyectado con `ui.head_content(ui.tags.script(...))`. Tras cada update
  reactivo hay que re-tipografiar (`MathJax.typesetPromise()`) — **verificar** que el
  re-typeset dispara bien con la reactividad de Shiny (posible `@render.ui` + script inline).
- Acordeones con derivación/contexto por concepto, más enlaces de referencia.

## Deploy

- GitHub Actions: `shinylive export . _site` → publica `_site/` en GitHub Pages en cada push.
- `.gitignore`: `_site/`, `.venv/`.

## Validación

- Tests de `solar/position.py` contra valores de referencia (NOAA / pvlib) en varias
  latitudes y fechas; tolerancia objetivo < 0.1° en elevación y azimut.
- Casos físicos sanity: subsolar en trópicos, sol de medianoche en círculos polares,
  azimut ≈ Norte a mediodía en verano para latitudes < 23.5°N.

## Roadmap

- **F1** Carta solar interactiva (numpy puro) + panel educativo. ← MVP
- **F2** Diseño de protecciones: ventana + alero/parteluz/celosía, máscara de sombreado, VSA/HSA.
- **F3** Irradiancia (pvlib cielo despejado), exportar CSV/figura, métricas verano/invierno.
