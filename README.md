# sun-protections

App web **interactiva y educativa** para visualizar la **trayectoria solar aparente** en
cualquier geolocalización y (en fases siguientes) **diseñar protecciones solares de
ventanas** (aleros, parteluces, celosías).

Corre **100 % en el navegador** vía [Shinylive](https://shiny.posit.co/py/docs/shinylive.html)
(Shiny for Python compilado a WebAssembly con Pyodide). Se publica como sitio **estático** en
GitHub Pages: **sin servidor**.

## Estado

**Fase 1 (carta solar) — completa.** Carta de trayectoria solar interactiva (cartesiana y
polar/estereográfica), curvas mensuales y de solsticios/equinoccios, analema horario,
posición del Sol en el instante elegido, orto/ocaso/mediodía solar/duración del día y panel
educativo con ecuaciones vivas (MathJax).

- **Fase 2** (en diseño): diseño de protecciones — ventana + alero/parteluz/celosía, máscara
  de sombreado, ángulos VSA/HSA, métricas verano/invierno.
- **Fase 3**: irradiancia incidente (pvlib, cielo despejado), exportar datos/figuras.

Ver [`DESIGN.md`](DESIGN.md) para la arquitectura y decisiones.

## Precisión

La posición solar usa el algoritmo **NOAA / Jean Meeus** implementado en **numpy puro** (sin
pvlib ni scipy en runtime → carga ligera). Validado contra el SPA de `pvlib`: error máximo
**~0.014° en elevación** y **~0.06° en azimut** para todo un año en latitudes de −34° a 70°.

## Desarrollo

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync                          # instala dependencias
uv run pytest                    # corre los tests (valida contra pvlib)
uv run shiny run app.py          # app de desarrollo en http://127.0.0.1:8000
```

### Exportar el sitio estático (como en producción)

```bash
uv run shinylive export . _site
uv run python -m http.server --directory _site --bind localhost 8008
```

> **Nota Pyodide:** `requirements.txt` declara los paquetes que el navegador instala en
> runtime. `tzdata` es imprescindible (zonas horarias); `numpy`/`matplotlib` los provee
> Pyodide. En la Fase 3 se añadirán `pvlib`, `scipy`, `h5py`.

## Estructura

```
app.py            UI Shiny (orquesta; no calcula)
solar/            núcleo de cálculo (numpy puro)
  position.py       posición solar NOAA/Meeus
  geometry.py       trayectorias, analema, eventos del día, zonas horarias
charts/sunpath.py renderizado matplotlib (cartesiana + polar)
data/cities.py    presets de ciudades
content/edu.py    ecuaciones vivas (LaTeX) + textos
tests/            validación (incl. contra pvlib)
```

## Despliegue

Cada push a `main` exporta y publica en **GitHub Pages** mediante GitHub Actions
(`.github/workflows/deploy.yml`).
