"""sun-protections — Fase 1: carta de trayectoria solar interactiva y educativa.

UI en Shiny for Python. Orquesta el núcleo solar (numpy puro), el renderizado matplotlib
y el panel educativo con ecuaciones vivas (MathJax). Pensado para exportarse con
``shinylive export`` y correr en GitHub Pages vía Pyodide, sin servidor.
"""

from __future__ import annotations

from datetime import date, datetime

from shiny import App, reactive, render, ui

from charts import render_sunpath, render_window_shadow
from solar.geometry import sun_at

# Temixco, Morelos (IER-UNAM) como latitud inicial.
TEMIXCO_LAT = 18.85

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_slider("lat", "Latitud (°)", min=-90, max=90, value=TEMIXCO_LAT, step=0.05),
        ui.hr(),
        ui.input_slider("fecha", "Fecha", min=date(2026, 1, 1), max=date(2026, 12, 31),
                        value=date(2026, 6, 21), time_format="%d %b"),
        ui.input_slider("hora", "Hora solar", min=0, max=24, value=12, step=0.25),
        ui.hr(),
        ui.input_checkbox("show_shading", "Protección: alero horizontal", value=True),
        ui.panel_conditional(
            "input.show_shading",
            ui.input_numeric("wall_az", "Orientación de la ventana (azimut °)",
                             value=180, min=0, max=360, step=5),
            ui.input_numeric("depth", "Profundidad del alero (m)", value=0.6, min=0, max=3, step=0.05),
            ui.input_numeric("win_h", "Alto de la ventana (m)", value=1.5, min=0.3, max=3, step=0.1),
            ui.input_numeric("win_w", "Ancho de la ventana (m)", value=1.2, min=0.3, max=4, step=0.1),
            ui.input_numeric("ext_left", "Extensión del alero · izquierda (m)",
                             value=0.0, min=0, max=2, step=0.1),
            ui.input_numeric("ext_right", "Extensión del alero · derecha (m)",
                             value=0.0, min=0, max=2, step=0.1),
            ui.input_numeric("offset", "Alero sobre el dintel (m)", value=0.0, min=0, max=1.5, step=0.05),
        ),
        title="Controles",
        width=300,
    ),
    ui.card(
        ui.card_header("Carta de trayectoria solar"),
        ui.output_plot("sunpath", height="600px"),
        full_screen=True,
    ),
    ui.card(
        ui.card_header("Ventana y sombra del alero"),
        ui.output_plot("window_diagram", height="430px"),
        full_screen=True,
    ),
    title="Sun-Protections · Trayectoria solar",
    fillable=False,
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
    def shading_spec():
        if not input.show_shading():
            return None

        def n(value, default):  # los input_numeric devuelven None si se vacían
            return default if value is None else float(value)

        return {"wall_az": n(input.wall_az(), 180.0), "depth": n(input.depth(), 0.6),
                "window_h": n(input.win_h(), 1.5), "window_w": n(input.win_w(), 1.2),
                "ext_left": n(input.ext_left(), 0.0), "ext_right": n(input.ext_right(), 0.0),
                "offset": n(input.offset(), 0.0)}

    @render.plot
    def sunpath():
        return render_sunpath(
            latitude(),
            current_dt=current_dt(),
            year=input.fecha().year,
            shading=shading_spec(),
        )

    @reactive.calc
    def sun_state() -> dict:
        return sun_at(current_dt(), latitude(), 0.0)

    @render.plot
    def window_diagram():
        sp = shading_spec()
        if sp is None:
            return _placeholder("Activa el alero para ver la sombra en la ventana")
        s = sun_state()
        return render_window_shadow(sp["wall_az"], sp["depth"], sp["window_h"], sp["window_w"],
                                    sp["offset"], s["azimuth"], s["apparent_elevation"],
                                    ext_left=sp["ext_left"], ext_right=sp["ext_right"])


app = App(app_ui, server)
