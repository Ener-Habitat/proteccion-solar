# sun-protections

App web **interactiva** para visualizar la **trayectoria solar aparente** y **diseñar
protecciones solares de ventanas** (alero horizontal con extensiones laterales).

Corre **100 % en el navegador** vía [Shinylive](https://shiny.posit.co/py/docs/shinylive.html)
(Shiny for Python compilado a WebAssembly con Pyodide). Se publica como sitio **estático** en
GitHub Pages: **sin servidor**.

## Qué hace

- **Carta de trayectoria solar estereográfica**: solsticios/equinoccios + 7 arcos de
  referencia, analema horario, día seleccionado en rojo con marcadores de hora y posición
  del Sol. Depende solo de **latitud + fecha + hora solar** (la longitud no afecta la
  trayectoria aparente).
- **Diseño de protección (alero)**: máscara de sombra total real proyectada sobre la carta,
  con los ángulos de corte **VSA** (profundidad) y **HSA** laterales (extensiones).
- **Esquema de ventana** en proyección ortográfica alineada (planta · sección · alzado) con
  la sombra real a la hora elegida y las cotas/ángulos relacionados.

## Precisión

La posición solar usa el algoritmo **NOAA / Jean Meeus** en **numpy puro** (sin pvlib ni
scipy en runtime → carga ligera). Validado contra el SPA de `pvlib`: error máximo
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
> runtime. La app usa solo `numpy` y `matplotlib` (ambos provistos por Pyodide); `pvlib`
> queda como dependencia de desarrollo (validación en los tests).

## Estructura

```
app.py              UI Shiny (orquesta; no calcula)
solar/
  position.py       posición solar NOAA/Meeus (numpy puro)
  geometry.py       trayectorias, analema, eventos del día (hora solar por longitud)
  shading.py        geometría de sombreado (VSA, HSA, fracción, malla)
charts/
  sunpath.py        carta estereográfica
  window.py         esquema de ventana (planta · sección · alzado)
tests/              validación (incl. contra pvlib)
```

## Despliegue

Cada push a `main` exporta y publica en **GitHub Pages** mediante GitHub Actions
(`.github/workflows/deploy.yml`).
