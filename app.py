"""sun-protections — carta de trayectoria solar interactiva y diseño de protecciones.

UI en Shiny for Python. Orquesta el núcleo solar (numpy puro) y el renderizado matplotlib
(carta estereográfica + esquema de ventana). Pensado para exportarse con
``shinylive export`` y correr en GitHub Pages vía Pyodide, sin servidor.
"""

from __future__ import annotations

import base64
import os
import re
import time
from datetime import date, datetime

from shiny import App, reactive, render, ui

from charts import render_sunpath, render_window_shadow
from solar.geometry import sun_at

# Temixco, Morelos (IER-UNAM) como latitud inicial.
TEMIXCO_LAT = 18.85

_DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def _methodology_markdown() -> str:
    """Lee docs/metodologia-sombra.md e incrusta las imágenes como data-URI (autónomo)."""
    try:
        text = open(os.path.join(_DOCS, "metodologia-sombra.md"), encoding="utf-8").read()
    except OSError:
        return "## Metodología\n\nDocumentación no disponible."

    def _inline(m):
        alt, src = m.group(1), m.group(2)
        try:
            data = base64.b64encode(open(os.path.join(_DOCS, src), "rb").read()).decode()
            return f"![{alt}](data:image/png;base64,{data})"
        except OSError:
            return m.group(0)

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _inline, text)


METHODOLOGY_MD = _methodology_markdown()

# Tema propio alineado a la paleta "pizarra" de las cartas (charts/sunpath.py): cuerpo en
# slate claro (#e9eef4-ish), texto slate (#2f3e4d), acento naranja de los arcos (#cf7a1e).
# CSS puro vía head_content → cero deps nuevas, compatible con Pyodide/Shinylive.
_BRAND = "#cf7a1e"        # naranja (analema/arcos de la carta)
_SLATE = "#2f3e4d"        # texto / header (color de texto de la carta "pizarra")
_THEME_CSS = f"""
:root {{
  --bs-body-bg: #eaf0f6;
  --bs-body-color: {_SLATE};
  --bs-emphasis-color: #1f2b38;
  --bs-secondary-color: #5f6f80;
  --bs-primary: {_BRAND};
  --bs-primary-rgb: 207,122,30;
  --bs-link-color: #b56716;
  --bs-link-hover-color: #94530f;
  --bs-border-color: #cfd9e6;
}}
body {{ background-color: #eaf0f6; color: {_SLATE}; }}

/* Barra de título (antes navbar de pestañas): slate oscuro con acento de marca. */
.navbar.navbar-static-top {{ background-color: {_SLATE}; border-bottom: 3px solid {_BRAND}; }}
.navbar .bslib-page-title, .navbar-brand {{ color: #f2f6fa; font-weight: 600; }}

/* Sidebar y cartas. */
.bslib-sidebar-layout > .sidebar {{ background-color: #e4ebf3; border-right: 1px solid #cfd9e6; }}
.sidebar-title {{ color: {_SLATE}; font-weight: 600; }}
.card.bslib-card {{ background-color: #fff; border: 1px solid #d6e0ec; border-radius: 12px;
  box-shadow: 0 1px 3px rgba(47,62,77,.06); }}

/* Acordeón con acento de marca al abrir. */
.accordion {{ --bs-accordion-bg: transparent; --bs-accordion-active-color: {_SLATE};
  --bs-accordion-active-bg: rgba(207,122,30,.10); --bs-accordion-border-color: #cfd9e6;
  --bs-accordion-btn-focus-box-shadow: 0 0 0 .2rem rgba(207,122,30,.25); }}

/* Foco y controles en color de marca. */
.form-control:focus, .form-select:focus {{ border-color: {_BRAND};
  box-shadow: 0 0 0 .2rem rgba(207,122,30,.20); }}
.form-check-input:checked {{ background-color: {_BRAND}; border-color: {_BRAND}; }}

/* Sliders (ionRangeSlider, skin "shiny"). */
.irs--shiny .irs-bar {{ background: {_BRAND}; border-color: {_BRAND}; }}
.irs--shiny .irs-handle {{ background-color: {_BRAND} !important; border: 1px solid {_BRAND} !important; }}
.irs--shiny .irs-handle:hover, .irs--shiny .irs-handle.state_hover {{ background-color: #b56716 !important; }}
.irs--shiny .irs-single, .irs--shiny .irs-from, .irs--shiny .irs-to {{ background-color: {_SLATE}; }}
.irs--shiny .irs-min, .irs--shiny .irs-max {{ color: #5f6f80; background: #dde6f0; }}

/* Cartas: cada card define su altura (responsiva) y su plot la llena; en móvil son pestañas
   y en escritorio (≥1200px) se muestran lado a lado, cada una con su botón de pantalla
   completa. */
#charts .card {{ height: clamp(360px, 72vh, 700px); }}
@media (min-width: 1200px) {{
  /* Ocultar la barra de pestañas y poner los dos paneles lado a lado. !important +
     flex-direction:row vencen el flex-column de .html-fill-container. */
  #charts .nav.nav-underline {{ display: none !important; }}
  #charts .tab-content {{ display: flex !important; flex-direction: row !important;
    gap: 1rem; align-items: stretch; }}
  #charts .tab-content > .tab-pane {{ display: block !important; flex: 1 1 0 !important;
    min-width: 0; }}
}}

/* La carta solar reserva margen amplio alrededor del círculo (layout "tight" con pad en
   charts/sunpath.py) para que ni el título ni N/S/E/O se corten sea cual sea la proporción
   del contenedor (retrato móvil ↔ apaisado de pestañas). */
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.accordion(
            ui.accordion_panel(
                "Ubicación y momento",
                ui.input_slider("lat", "Latitud (°)", min=-90, max=90,
                                value=TEMIXCO_LAT, step=0.05),
                ui.input_slider("fecha", "Fecha", min=date(2026, 1, 1),
                                max=date(2026, 12, 31), value=date(2026, 6, 21),
                                time_format="%d %b"),
                ui.input_slider("hora", "Hora solar", min=0, max=24, value=12, step=0.25),
            ),
            ui.accordion_panel(
                "Apariencia",
                ui.input_select("shade_method", "Máscara de sombra",
                                choices={"practico": "Práctico (99.9999% área)",
                                         "analitico": "100% analítico (cerrado)",
                                         "raycast": "100% ray casting"},
                                selected="practico"),
                ui.input_checkbox("show_protractor",
                                  "Transportador (arcos VSA / rectas HSA)", value=False),
            ),
            ui.accordion_panel(
                "Protección solar",
                ui.input_checkbox("show_shading", "Protección solar (celosía)", value=True),
                ui.panel_conditional(
                    "input.show_shading",
                    ui.accordion(
                        ui.accordion_panel(
                            "Ventana",
                            ui.input_numeric("wall_az", "Orientación (azimut °)",
                                             value=180, min=0, max=360, step=5),
                            ui.input_numeric("win_h", "Alto (m)", value=1.5,
                                             min=0.3, max=3, step=0.1),
                            ui.input_numeric("win_w", "Ancho (m)", value=1.2,
                                             min=0.3, max=4, step=0.1),
                        ),
                        ui.accordion_panel(
                            "Alero horizontal",
                            ui.input_numeric("depth", "Profundidad (m)", value=0.6,
                                             min=0, max=3, step=0.05),
                            ui.input_numeric("ext_left", "Extensión · izquierda (m)",
                                             value=0.0, min=0, max=2, step=0.1),
                            ui.input_numeric("ext_right", "Extensión · derecha (m)",
                                             value=0.0, min=0, max=2, step=0.1),
                            ui.input_numeric("offset", "Separación sobre el dintel (m)",
                                             value=0.0, min=0, max=1.5, step=0.05),
                        ),
                        ui.accordion_panel(
                            "Aletas verticales (parasoles)",
                            ui.input_numeric("fin_left", "Aleta izquierda · profundidad (m)",
                                             value=0.0, min=0, max=2, step=0.05),
                            ui.input_numeric("fin_right", "Aleta derecha · profundidad (m)",
                                             value=0.0, min=0, max=2, step=0.05),
                        ),
                        id="acc_proteccion",
                        open=["Ventana", "Alero horizontal"],
                        multiple=True,
                    ),
                ),
            ),
            id="acc_main",
            # Arranca solo con "Ubicación y momento" abierto; el resto colapsado hacia arriba.
            open=["Ubicación y momento"],
            multiple=True,
        ),
        width=320,
        # En móvil lo dejamos colapsado (botón/overlay) para que no se apile debajo del
        # contenido y empuje las cartas hasta el fondo.
        open={"desktop": "open", "mobile": "closed"},
    ),
    # Cartas: pestañas en móvil (una a la vez, ocupa el alto útil) que el CSS convierte en
    # lado-a-lado en escritorio (≥1200px). Un solo juego de outputs → no duplica renders.
    ui.div(
        ui.navset_underline(
            ui.nav_panel("Carta solar",
                         ui.card(ui.output_plot("sunpath", height="100%"), full_screen=True)),
            ui.nav_panel("Ventana",
                         ui.card(ui.output_plot("window_diagram", height="100%"), full_screen=True)),
            id="charts_tabs",
        ),
        id="charts",
    ),
    ui.head_content(ui.tags.style(_THEME_CSS)),
    # Metodología (METHODOLOGY_MD) quedó fuera al pasar a una sola vista; reintroducir como
    # ui.page_navbar + nav_panel solo si vuelve a haber ≥2 secciones.
    title="Protección solar",
)


def _clamp(value, lo: float, hi: float, default: float) -> float:
    """Limita un input numérico a [lo, hi]; usa default si viene vacío (None)."""
    if value is None:
        return default
    return max(lo, min(hi, float(value)))


def _placeholder(text: str):
    """Figura con un mensaje centrado (cuando no hay nada que dibujar)."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 4))
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color="#888")
    ax.axis("off")
    return fig


def _debounce(read, delay: float = 0.25):
    """Versión "debounced" de una expresión reactiva: emite el último valor sólo cuando
    deja de cambiar durante ``delay`` segundos (evita la avalancha de renders al arrastrar).

    Devuelve un ``reactive.value`` que se lee como ``salida()``.
    """
    out = reactive.value(None)
    stamp = reactive.value(None)

    @reactive.effect
    def _watch():
        v = read()                       # dependencia: la(s) entrada(s) en vivo
        stamp.set((v, time.monotonic()))

    @reactive.effect
    def _emit():
        s = stamp()                      # dependencia: cada cambio reprograma
        if s is None:
            return
        v, t = s
        with reactive.isolate():
            first = out() is None
        if first:                        # el primer valor se emite de inmediato
            out.set(v)
            return
        elapsed = time.monotonic() - t
        if elapsed >= delay:
            out.set(v)
        else:
            reactive.invalidate_later(delay - elapsed)

    return out


def server(input, output, session):
    @reactive.calc
    def latitude() -> float:
        """Latitud validada (clamp a rango físico)."""
        return _clamp(input.lat(), -90.0, 90.0, 0.0)

    @reactive.calc
    def current_dt() -> datetime:
        d: date = input.fecha()
        h = input.hora()
        hour = int(h)
        minute = int(round((h - hour) * 60))
        if hour >= 24:
            hour, minute = 23, 59
        return datetime(d.year, d.month, d.day, hour, minute)

    @reactive.calc
    def _raw():
        """Todos los parámetros que disparan recálculo (lat, instante, alero)."""
        def n(value, default):  # los input_numeric devuelven None si se vacían
            return default if value is None else float(value)

        spec = None
        if input.show_shading():
            spec = {"wall_az": n(input.wall_az(), 180.0), "depth": n(input.depth(), 0.6),
                    "window_h": n(input.win_h(), 1.5), "window_w": n(input.win_w(), 1.2),
                    "ext_left": n(input.ext_left(), 0.0), "ext_right": n(input.ext_right(), 0.0),
                    "offset": n(input.offset(), 0.0),
                    "fin_left": n(input.fin_left(), 0.0), "fin_right": n(input.fin_right(), 0.0)}
        return (latitude(), current_dt(), spec)

    # Un solo snapshot "debounced": todo se recalcula al SOLTAR (tras una breve pausa),
    # sin avalancha mientras arrastras. Carta y esquema de ventana usan el mismo snapshot.
    snap = _debounce(_raw, 0.3)

    @render.plot
    def sunpath():
        s = snap()
        if s is None:
            return _placeholder("…")
        lat, dt, spec = s
        return render_sunpath(lat, current_dt=dt, year=dt.year, shading=spec,
                              shade_method=input.shade_method(),
                              show_protractor=input.show_protractor())

    @render.plot
    def window_diagram():
        s = snap()
        if s is None or s[2] is None:
            return _placeholder("Activa la protección para ver la sombra en la ventana")
        lat, dt, spec = s
        sun = sun_at(dt, lat, 0.0)
        return render_window_shadow(spec["wall_az"], spec["depth"], spec["window_h"],
                                    spec["window_w"], spec["offset"],
                                    sun["azimuth"], sun["apparent_elevation"],
                                    ext_left=spec["ext_left"], ext_right=spec["ext_right"],
                                    fin_left=spec["fin_left"], fin_right=spec["fin_right"])


app = App(app_ui, server)
