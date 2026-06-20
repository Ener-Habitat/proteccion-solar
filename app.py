"""sun-protections — Fase 1: carta de trayectoria solar interactiva y educativa.

UI en Shiny for Python. Orquesta el núcleo solar (numpy puro), el renderizado matplotlib
y el panel educativo con ecuaciones vivas (MathJax). Pensado para exportarse con
``shinylive export`` y correr en GitHub Pages vía Pyodide, sin servidor.
"""

from __future__ import annotations

from datetime import date, datetime

from shiny import App, reactive, render, ui

from charts import render_sunpath
from content import CONCEPTS, live_equations_html
from data import CITIES, DEFAULT_CITY, TIMEZONES
from solar.geometry import day_events, sun_at

# --- MathJax: tipografía las ecuaciones vivas; re-typeset al actualizarse el panel. ---
_MATHJAX = ui.head_content(
    ui.tags.script(
        """
        window.MathJax = { tex: { inlineMath: [['\\\\(','\\\\)']],
                                  displayMath: [['\\\\[','\\\\]']] },
                           options: { skipHtmlTags: ['script','noscript','style','textarea'] } };
        """
    ),
    ui.tags.script(src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js", **{"async": ""}),
    ui.tags.script(
        """
        // Re-tipografiar SÓLO cuando Shiny actualiza la salida de ecuaciones.
        // (Evitamos un MutationObserver global: MathJax modifica el DOM al tipografiar,
        //  lo que realimentaría al observer en un bucle infinito que cuelga la página.)
        $(document).on('shiny:value', function (e) {
          if (e.name && e.name.endsWith('equations')) {
            setTimeout(function () {
              var el = document.getElementById('equations');
              if (el && window.MathJax && MathJax.typesetPromise) {
                MathJax.typesetPromise([el]);
              }
            }, 0);
          }
        });
        """
    ),
)

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select("city", "Ciudad", choices=list(CITIES.keys()), selected=DEFAULT_CITY),
        ui.input_numeric("lat", "Latitud (°)", value=CITIES[DEFAULT_CITY][0], min=-90, max=90, step=0.01),
        ui.input_numeric("lon", "Longitud (°)", value=CITIES[DEFAULT_CITY][1], min=-180, max=180, step=0.01),
        ui.input_select("tz", "Zona horaria", choices=TIMEZONES, selected=CITIES[DEFAULT_CITY][2]),
        ui.hr(),
        ui.input_slider("fecha", "Fecha", min=date(2026, 1, 1), max=date(2026, 12, 31),
                        value=date(2026, 6, 21), time_format="%d %b"),
        ui.input_slider("hora", "Hora local", min=0, max=24, value=12, step=0.25),
        ui.input_checkbox("show_sun", "Marcar posición del Sol", value=True),
        ui.hr(),
        ui.input_radio_buttons("projection", "Proyección",
                               {"cartesian": "Cartesiana", "polar": "Polar"}, selected="cartesian"),
        ui.input_radio_buttons("curves", "Curvas",
                               {"monthly": "Mensuales", "solstices": "Solsticios/equinoccios"},
                               selected="monthly"),
        ui.input_radio_buttons("azconv", "Azimut",
                               {"N0": "Norte = 0°", "S0": "Sur = 0°"}, selected="N0"),
        ui.input_checkbox("analemma", "Mostrar analema horario", value=True),
        title="Controles",
        width=300,
    ),
    ui.layout_columns(
        ui.card(
            ui.card_header("Carta de trayectoria solar"),
            ui.output_plot("sunpath", height="600px"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Posición solar (instante seleccionado)"),
            ui.output_ui("sun_data"),
        ),
        col_widths=[8, 4],
    ),
    ui.card(
        ui.card_header("Ecuaciones (valores actuales)"),
        ui.output_ui("equations"),
    ),
    ui.card(
        ui.card_header("¿Qué es esto?"),
        ui.accordion(
            *[ui.accordion_panel(title, ui.markdown(text)) for title, text in CONCEPTS.items()],
            open=False,
            multiple=True,
        ),
    ),
    _MATHJAX,
    title="Sun-Protections · Trayectoria solar",
    fillable=False,
)


def _clamp(value, lo: float, hi: float, default: float) -> float:
    """Limita un input numérico a [lo, hi]; usa default si viene vacío (None)."""
    if value is None:
        return default
    return max(lo, min(hi, float(value)))


def _hhmm(hours_decimal) -> str:
    """Formatea una hora decimal local a 'HH:MM' (o '—' si no aplica)."""
    if hours_decimal is None:
        return "—"
    h = int(hours_decimal) % 24
    m = int(round((hours_decimal - int(hours_decimal)) * 60))
    if m == 60:
        h, m = (h + 1) % 24, 0
    return f"{h:02d}:{m:02d}"


def server(input, output, session):
    @reactive.effect
    @reactive.event(input.city)
    def _sync_city():
        lat, lon, tz = CITIES[input.city()]
        ui.update_numeric("lat", value=lat)
        ui.update_numeric("lon", value=lon)
        ui.update_select("tz", selected=tz)

    @reactive.calc
    def loc() -> tuple[float, float, str]:
        """Lat/lon validados (clamp a rango físico) y zona horaria."""
        return (_clamp(input.lat(), -90.0, 90.0, 0.0),
                _clamp(input.lon(), -180.0, 180.0, 0.0),
                input.tz())

    @reactive.calc
    def current_dt() -> datetime:
        d: date = input.fecha()
        h = input.hora()
        hour = int(h)
        minute = int(round((h - hour) * 60))
        if hour >= 24:
            hour, minute = 23, 59
        return datetime(d.year, d.month, d.day, hour, minute)

    @render.plot
    def sunpath():
        lat, lon, tz = loc()
        return render_sunpath(
            lat, lon, tz,
            projection=input.projection(),
            azimuth_convention=input.azconv(),
            curves=input.curves(),
            show_analemma=input.analemma(),
            current_dt=current_dt() if input.show_sun() else None,
            year=input.fecha().year,
        )

    @reactive.calc
    def sun_state() -> dict:
        lat, lon, tz = loc()
        return sun_at(current_dt(), lat, lon, tz)

    @reactive.calc
    def events() -> dict:
        lat, lon, tz = loc()
        return day_events(input.fecha().isoformat(), lat, lon, tz)

    @render.ui
    def sun_data():
        s = sun_state()
        ev = events()
        below = s["apparent_elevation"] <= 0
        rows = [
            ("Elevación aparente", f"{s['apparent_elevation']:.2f}°"),
            ("Azimut", f"{s['azimuth']:.2f}°"),
            ("Ángulo cenital", f"{s['zenith']:.2f}°"),
            ("Declinación δ", f"{s['declination']:.2f}°"),
            ("Ecuación del tiempo", f"{s['equation_of_time']:+.2f} min"),
            ("Ángulo horario H", f"{s['hour_angle']:+.2f}°"),
        ]
        if ev["polar_night"]:
            day_rows = [("Día/noche polar", "🌑 Noche polar (sin orto)")]
        elif ev["polar_day"]:
            day_rows = [("Día/noche polar", "☀️ Sol de medianoche (24 h)"),
                        ("Elevación máx.", f"{ev['max_elevation']:.2f}°")]
        else:
            day_rows = [
                ("Orto (salida)", _hhmm(ev["sunrise"])),
                ("Mediodía solar", _hhmm(ev["solar_noon"])),
                ("Ocaso (puesta)", _hhmm(ev["sunset"])),
                ("Duración del día", f"{ev['day_length']:.2f} h"),
                ("Elevación máx.", f"{ev['max_elevation']:.2f}°"),
            ]

        def table(title, data):
            return ui.TagList(
                ui.tags.h6(title, {"class": "text-muted mt-2"}),
                ui.tags.table({"class": "table table-sm mb-1"},
                              ui.tags.tbody(*[ui.tags.tr(ui.tags.td(ui.tags.b(k)),
                                                         ui.tags.td(v)) for k, v in data])),
            )

        note = ui.tags.p({"class": "text-muted"}, "🌙 El Sol está bajo el horizonte.") if below else None
        return ui.TagList(table("Instante", rows), note, table("Día", day_rows))

    @render.ui
    def equations():
        return ui.HTML(live_equations_html(sun_state(), input.lat()))


app = App(app_ui, server)
