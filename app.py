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

# Tema "golden hour" alineado a la paleta de las cartas (charts/sunpath.py): base slate fría,
# acento ámbar cálido en degradado (sol), tarjetas claras con sombras suaves. CSS puro vía
# head_content → cero deps nuevas, compatible con Pyodide/Shinylive. La tipografía usa una
# pila de sistema (sin red): elegante y con fallback inmediato si no hay fuente externa.
_BRAND = "#cf7a1e"        # naranja quemado (analema/arcos de la carta)
_AMBER = "#f5a623"        # ámbar cálido (extremo claro del degradado "sol")
_SLATE = "#2f3e4d"        # texto / header (color de texto de la carta "pizarra")
_INK = "#1d2935"          # slate profundo (énfasis / fondo de header)
_THEME_CSS = f"""
:root {{
  --bs-body-bg: #eef3f9;
  --bs-body-color: {_SLATE};
  --bs-emphasis-color: {_INK};
  --bs-secondary-color: #66788a;
  --bs-primary: {_BRAND};
  --bs-primary-rgb: 207,122,30;
  --bs-link-color: #b56716;
  --bs-link-hover-color: #94530f;
  --bs-border-color: #d3deeb;
  --bs-body-font-family: "Inter", "Segoe UI", -apple-system, BlinkMacSystemFont,
    "Helvetica Neue", Arial, sans-serif;
  --sun: linear-gradient(135deg, {_AMBER} 0%, {_BRAND} 100%);
}}
* {{ -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}

/* Fondo del cuerpo: degradado lavanda-frío muy sutil, evoca el cielo. */
body {{
  background: radial-gradient(1200px 600px at 78% -8%, #fff6e8 0%, rgba(255,246,232,0) 55%),
              linear-gradient(180deg, #eef3f9 0%, #e4ecf5 100%) fixed;
  color: {_SLATE};
  letter-spacing: .1px;
}}

/* ── Cabecera (barra de título) ───────────────────────────────────────────────
   Slate profundo con un sutil brillo dorado a la derecha (sol naciente) y una
   fina línea de degradado ámbar abajo. */
.navbar.navbar-static-top {{
  background: radial-gradient(640px 220px at 92% -40%, rgba(245,166,35,.28) 0%, rgba(245,166,35,0) 60%),
              linear-gradient(120deg, {_INK} 0%, {_SLATE} 100%);
  border-bottom: none;
  box-shadow: 0 2px 18px rgba(29,41,53,.22);
  position: relative;
  padding-top: .5rem; padding-bottom: .5rem;
}}
.navbar.navbar-static-top::after {{
  content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: linear-gradient(90deg, {_AMBER}, {_BRAND} 60%, rgba(207,122,30,0));
}}
.navbar .bslib-page-title, .navbar-brand {{ color: #f4f8fc; font-weight: 700;
  letter-spacing: .2px; }}
/* Subtítulo (la app pasa el título como bloque con dos líneas). */
.app-title {{ display: flex; align-items: center; gap: .6rem; line-height: 1.05; }}
.app-title .sun-dot {{ width: 18px; height: 18px; border-radius: 50%;
  background: var(--sun); box-shadow: 0 0 0 4px rgba(245,166,35,.18),
  0 0 16px 2px rgba(245,166,35,.45); flex: none; }}
.app-title small {{ display: block; font-weight: 500; font-size: .68rem;
  letter-spacing: 1.4px; text-transform: uppercase; color: #9fb2c6; margin-top: 2px; }}

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
.bslib-sidebar-layout > .sidebar {{
  background: linear-gradient(180deg, #eaf1f8 0%, #e2eaf4 100%);
  border-right: 1px solid #d3deeb;
}}
.bslib-sidebar-layout > .sidebar .sidebar-content {{ padding-top: .85rem; }}
.sidebar-title {{ color: {_SLATE}; font-weight: 700; }}
.control-label {{ font-weight: 600; font-size: .82rem; color: #4a5b6c;
  letter-spacing: .2px; }}

/* ── Tarjetas ─────────────────────────────────────────────────────────────── */
.card.bslib-card {{
  background: #ffffff;
  border: 1px solid #e0e8f1;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(29,41,53,.04), 0 8px 24px -12px rgba(29,41,53,.18);
  transition: box-shadow .25s ease, transform .25s ease;
}}
.card.bslib-card:hover {{
  box-shadow: 0 2px 4px rgba(29,41,53,.06), 0 16px 36px -14px rgba(29,41,53,.28);
}}
.card.bslib-card > .card-body {{ padding: .75rem; }}

/* ── Acordeón ─────────────────────────────────────────────────────────────── */
.accordion {{ --bs-accordion-bg: transparent; --bs-accordion-active-color: {_INK};
  --bs-accordion-active-bg: rgba(245,166,35,.12); --bs-accordion-border-color: #d3deeb;
  --bs-accordion-btn-focus-box-shadow: 0 0 0 .2rem rgba(245,166,35,.25);
  --bs-accordion-border-radius: 12px; }}
.accordion-item {{ border-radius: 12px !important; overflow: hidden; margin-bottom: .4rem;
  border: 1px solid #d8e2ee; }}
.accordion-button {{ font-weight: 600; color: {_SLATE}; }}
.accordion-button:not(.collapsed) {{ box-shadow: none;
  border-left: 3px solid {_BRAND}; }}
.accordion-button::after {{ filter: saturate(0) brightness(.6); }}
.accordion-button:not(.collapsed)::after {{ filter: none; }}

/* ── Controles ────────────────────────────────────────────────────────────── */
.form-control, .form-select {{ border-radius: 9px; border-color: #cdd9e7;
  transition: border-color .15s ease, box-shadow .15s ease; }}
.form-control:focus, .form-select:focus {{ border-color: {_BRAND};
  box-shadow: 0 0 0 .2rem rgba(245,166,35,.22); }}
.form-check-input:checked {{ background-color: {_BRAND}; border-color: {_BRAND}; }}
.form-check-input:focus {{ box-shadow: 0 0 0 .2rem rgba(245,166,35,.22); }}

/* ── Sliders (ionRangeSlider, skin "shiny") ──────────────────────────────────
   Barra con degradado "sol" y manija con halo dorado al pasar el ratón. */
.irs--shiny .irs-line {{ background: #d7e1ee; border: none; border-radius: 6px; height: 6px; }}
.irs--shiny .irs-bar {{ background: var(--sun); border: none; height: 6px; }}
.irs--shiny .irs-handle {{ background: #ffffff !important; border: 2px solid {_BRAND} !important;
  box-shadow: 0 1px 4px rgba(29,41,53,.25) !important; top: 22px; width: 18px; height: 18px;
  transition: box-shadow .15s ease; }}
.irs--shiny .irs-handle:hover, .irs--shiny .irs-handle.state_hover {{
  box-shadow: 0 0 0 5px rgba(245,166,35,.22), 0 1px 4px rgba(29,41,53,.25) !important; }}
.irs--shiny .irs-single, .irs--shiny .irs-from, .irs--shiny .irs-to {{
  background-color: {_INK}; border-radius: 6px; font-weight: 600; }}
.irs--shiny .irs-single::before, .irs--shiny .irs-from::before, .irs--shiny .irs-to::before {{
  border-top-color: {_INK}; }}
.irs--shiny .irs-min, .irs--shiny .irs-max {{ color: #66788a; background: #dde6f0;
  border-radius: 6px; }}

/* ── Cartas: responsivas (pestañas en móvil → lado a lado en ≥1200px) ──────── */
#charts {{ padding: .25rem; }}
#charts .card {{ height: clamp(360px, 72vh, 720px); }}
#charts .nav-underline .nav-link {{ font-weight: 600; color: #66788a; }}
#charts .nav-underline .nav-link.active {{ color: {_BRAND};
  border-bottom-color: {_BRAND}; }}
@media (min-width: 1200px) {{
  /* Ocultar la barra de pestañas y poner los dos paneles lado a lado. !important +
     flex-direction:row vencen el flex-column de .html-fill-container. */
  #charts .nav.nav-underline {{ display: none !important; }}
  #charts .tab-content {{ display: flex !important; flex-direction: row !important;
    gap: 1.1rem; align-items: stretch; }}
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
    title=ui.div(
        ui.span(class_="sun-dot"),
        ui.div(
            ui.span("Protección solar"),
            ui.tags.small("Trayectoria solar · diseño de aleros"),
        ),
        class_="app-title",
    ),
    window_title="Protección solar",
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
