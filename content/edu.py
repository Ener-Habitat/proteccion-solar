"""Contenido educativo: ecuaciones vivas (LaTeX) y textos de conceptos.

``live_equations_html`` genera un bloque HTML con las fórmulas clave de geometría solar y
los **valores actuales sustituidos**, para que MathJax lo tipografíe. ``CONCEPTS`` son los
textos de los acordeones explicativos. Sin dependencias de Shiny: sólo strings, testeable.
"""

from __future__ import annotations


def live_equations_html(sp: dict, latitude: float) -> str:
    """HTML con las ecuaciones solares evaluadas en el instante actual.

    ``sp`` es la salida escalar de ``solar.geometry.sun_at``.
    Usa delimitadores ``\\(...\\)`` / ``\\[...\\]`` que MathJax tipografía.
    """
    decl = sp["declination"]
    eot = sp["equation_of_time"]
    H = sp["hour_angle"]
    elev = sp["apparent_elevation"]
    elev_geom = sp["elevation"]
    az = sp["azimuth"]
    zen = sp["zenith"]
    phi = latitude

    return f"""
<div class="live-eq">
  <p><b>Declinación solar</b> — inclinación del Sol respecto al ecuador celeste:</p>
  \\[ \\delta = \\arcsin\\!\\big(\\sin\\varepsilon \\, \\sin\\lambda\\big) = {decl:.2f}^\\circ \\]

  <p><b>Ecuación del tiempo</b> — desfase entre el mediodía solar y el del reloj:</p>
  \\[ E = {eot:+.2f}\\ \\text{{min}} \\]

  <p><b>Ángulo horario</b> — posición del Sol en su giro diario (0° = mediodía solar):</p>
  \\[ H = {H:+.2f}^\\circ \\]

  <p><b>Elevación solar</b> — altura del Sol sobre el horizonte:</p>
  \\[ \\sin\\alpha = \\sin\\phi\\,\\sin\\delta + \\cos\\phi\\,\\cos\\delta\\,\\cos H \\]
  \\[ \\phi={phi:.2f}^\\circ,\\quad \\alpha_\\text{{geom}} = {elev_geom:.2f}^\\circ,\\quad
     \\alpha_\\text{{aparente}} = {elev:.2f}^\\circ \\]

  <p><b>Ángulo cenital</b> y <b>azimut</b>:</p>
  \\[ z = 90^\\circ - \\alpha = {zen:.2f}^\\circ, \\qquad A = {az:.2f}^\\circ \\]
</div>
"""


# {título: markdown} para los acordeones explicativos.
CONCEPTS = {
    "¿Qué es la carta de trayectoria solar?": (
        "Representa la posición del Sol (azimut y elevación) a lo largo del día y del año "
        "para un sitio. Cada curva es un día; el patrón en forma de **8** punteado (analema) "
        "une la posición del Sol a una misma hora a lo largo del año. Permite ver de un "
        "vistazo de dónde y a qué altura llega el Sol en cada estación."
    ),
    "Azimut y elevación": (
        "El **azimut** (A) es la dirección de la brújula hacia el Sol; aquí, por defecto, "
        "Norte = 0° y aumenta en sentido horario (E=90°, S=180°, W=270°). La **elevación** "
        "(α) es la altura angular sobre el horizonte (0° en el horizonte, 90° en el cenit). "
        "El **ángulo cenital** es su complemento, z = 90° − α."
    ),
    "Declinación y estaciones": (
        "La **declinación** δ varía entre ±23.45° a lo largo del año por la inclinación del "
        "eje terrestre. En el solsticio de verano del hemisferio norte δ ≈ +23.45° y el Sol "
        "alcanza su mayor altura; en el de invierno δ ≈ −23.45°. En los equinoccios δ ≈ 0° y "
        "el Sol sale exactamente por el Este y se pone por el Oeste."
    ),
    "Ecuación del tiempo y hora solar": (
        "El **mediodía solar** (Sol en su punto más alto) casi nunca coincide con las 12:00 "
        "del reloj. La **ecuación del tiempo** E corrige ese desfase (hasta ±16 min) por la "
        "órbita elíptica y la inclinación axial. La carta usa **hora solar estándar local** "
        "(sin horario de verano) para evitar saltos artificiales en las curvas."
    ),
    "Refracción atmosférica": (
        "La atmósfera **desvía** la luz solar, haciendo que el Sol se vea más alto de lo que "
        "está geométricamente, sobre todo cerca del horizonte (hasta ~0.5°). Por eso "
        "distinguimos la elevación **geométrica** de la **aparente**, que es la que se observa."
    ),
    "Exactitud del cálculo": (
        "La posición solar se calcula con el algoritmo de NOAA/Meeus en numpy puro. Validado "
        "contra el SPA de pvlib, el error máximo es ~0.014° en elevación y ~0.06° en azimut "
        "para todo un año en latitudes de −34° a 70°: precisión apta para ingeniería."
    ),
}
