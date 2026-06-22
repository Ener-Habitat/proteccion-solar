"""Esquema de ventana + sombra del alero en proyección ortográfica alineada.

Tres vistas en un único sistema de coordenadas (misma escala) dispuestas como en dibujo
técnico:

        ┌── Planta ──┐        (ancho = ventana, alto = profundidad)
  ┌Sec┐ ┌── Alzado ──┐        (Sección: ancho = profundidad, alto = ventana)
  └───┘ └────────────┘

Así las cotas se leen entre vistas: la **profundidad** es la misma en Sección y Planta, el
**ancho** se comparte Planta↔Alzado y el **alto** Sección↔Alzado. Se marcan el **VSA**
(sección, profundidad vs. alto) y los **HSA laterales** (planta, profundidad vs. extensión).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mp
import matplotlib.pyplot as plt
import numpy as np

from solar import shading as shd

_SHADE = "#27c2d6"
_SUN = "#f6d65b"
_WALL = "#4a4a4a"
_NOSUN = "#c9ccd1"
_ANG = "#a06b00"
_GLASS = "#7fbfd0"


def _angle_arc(ax, center, theta1, theta2, radius, label, lab_r=1.5):
    ax.add_patch(mp.Arc(center, 2 * radius, 2 * radius, angle=0, theta1=theta1, theta2=theta2,
                        color=_ANG, lw=1.2, zorder=6))
    mid = np.radians((theta1 + theta2) / 2)
    ax.annotate(label, (center[0] + lab_r * radius * np.cos(mid), center[1] + lab_r * radius * np.sin(mid)),
                fontsize=7.5, color=_ANG, ha="center", va="center", zorder=7)


def render_window_shadow(wall_az: float, depth: float, window_h: float, window_w: float,
                         offset: float, sun_az: float, sun_elev: float, ext_left: float = 0.0,
                         ext_right: float = 0.0, fin_left: float = 0.0, fin_right: float = 0.0,
                         ext_top: float = 0.0):
    """Esquema alineado (planta + sección + alzado) con la sombra real de la celosía."""
    lit = shd.illuminated(sun_az, sun_elev, wall_az)
    vsa = float(shd.vertical_shadow_angle(sun_az, sun_elev, wall_az)) if lit else float("nan")
    X, Y, blocked = shd.window_shade_grid(wall_az, depth, window_w, window_h, offset,
                                          ext_left, ext_right, sun_az, sun_elev,
                                          fin_left, fin_right, ext_top)
    frac = float(blocked.mean()) if lit else 0.0
    shadow_y = float(np.clip((window_h + offset) - depth * np.tan(np.radians(vsa)), 0, window_h)) if lit else window_h

    top = window_h + offset                 # altura del alero sobre el antepecho
    gap = max(0.28, 0.18 * window_h)        # separación entre vistas
    xL, xR = -ext_left, window_w + ext_right
    py0 = top + gap                         # línea de pared de la PLANTA (arriba del alzado)
    sx0 = xL - gap                          # línea de pared de la SECCIÓN (izq. del alzado)

    fig, ax = plt.subplots(figsize=(10.5, 5.2))

    _alzado(ax, X, Y, blocked, lit, window_w, window_h, top, xL, xR, ext_left, ext_right)
    _planta(ax, depth, window_w, ext_left, ext_right, xL, xR, py0, fin_left, fin_right)
    _seccion(ax, depth, window_h, top, shadow_y, lit, sx0)

    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(sx0 - depth - 0.5, xR + 0.5)
    ax.set_ylim(-0.55, py0 + depth + 0.45)

    title = ("Sin sol directo sobre la ventana" if (not lit and sun_elev > 0)
             else "Sol bajo el horizonte" if not lit
             else f"Ventana {frac * 100:.0f}% sombreada")
    ax.set_title(title, fontsize=11, color="#444" if lit else "#888")
    fig.tight_layout()
    return fig


def _alzado(ax, X, Y, blocked, lit, window_w, window_h, top, xL, xR, ext_left, ext_right):
    """Vista frontal con la sombra real (bloque central)."""
    if not lit:
        ax.add_patch(mp.Rectangle((0, 0), window_w, window_h, facecolor=_NOSUN, edgecolor="none"))
    else:
        cmap = mcolors.ListedColormap([_SUN, _SHADE])
        ax.pcolormesh(X, Y, blocked.astype(float), cmap=cmap, vmin=0, vmax=1, shading="auto", zorder=1)
        bf = blocked.astype(float)
        if 0.0 < bf.mean() < 1.0:
            ax.contour(X, Y, bf, levels=[0.5], colors=[_ANG], linewidths=1.5, linestyles="--", zorder=2)
    ax.add_patch(mp.Rectangle((0, 0), window_w, window_h, fill=False, edgecolor=_WALL, lw=2.2, zorder=3))
    # Alero de frente (ancho total) y cotas de extensión.
    ax.plot([xL, xR], [top, top], color=_WALL, lw=4, solid_capstyle="round", zorder=4)
    for x0, x1, ext in [(-ext_left, 0.0, ext_left), (window_w, window_w + ext_right, ext_right)]:
        if ext > 0:
            yd = top + 0.12
            ax.annotate("", (x1, yd), (x0, yd), arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))
            ax.text((x0 + x1) / 2, yd + 0.02, f"{ext:.1f}", fontsize=6.5, color="#666", ha="center", va="bottom")

    # Cotas de la VENTANA: ancho (abajo) y alto (derecha).
    yw = -0.2
    ax.annotate("", (window_w, yw), (0, yw), arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))
    ax.text(window_w / 2, yw - 0.03, f"ancho {window_w:.2f} m", fontsize=6.5, color="#666",
            ha="center", va="top")
    xh = xR + 0.2
    ax.annotate("", (xh, window_h), (xh, 0), arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))
    ax.text(xh + 0.05, window_h / 2, f"alto {window_h:.2f} m", fontsize=6.5, color="#666",
            ha="center", va="center", rotation=90)

    ax.text(window_w / 2, -0.46, "Alzado (frente)", fontsize=9, ha="center", va="center", color="#444")


def _planta(ax, depth, window_w, ext_left, ext_right, xL, xR, py0, fin_left=0.0, fin_right=0.0):
    """Vista superior (arriba del alzado): alero (rectángulo), aletas (a los costados) y los
    ángulos HSA (de la aleta si la hay, o del alero por su extensión)."""
    if depth > 0:
        ax.add_patch(mp.Rectangle((xL, py0), xR - xL, depth, facecolor="#eceff1",
                                  edgecolor=_WALL, lw=1.2, zorder=2))
    ax.plot([xL - 0.25, xR + 0.25], [py0, py0], color=_WALL, lw=2.5, zorder=3)
    ax.plot([0, window_w], [py0, py0], color=_GLASS, lw=6, solid_capstyle="butt", zorder=4)  # ventana
    top_y = py0 + max(depth, fin_left, fin_right)

    if depth > 0:                                    # cota de profundidad del alero
        xd = xL - 0.16
        ax.annotate("", (xd, py0), (xd, py0 + depth), arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))
        ax.text(xd - 0.06, py0 + depth / 2, f"prof. {depth:.2f}", fontsize=6.5, color="#666",
                ha="center", va="center", rotation=90)

    for sign, edge_x, ext, fin, lbl in ((+1, window_w, ext_right, fin_right, "der."),
                                        (-1, 0.0, ext_left, fin_left, "izq.")):
        if fin > 0:
            # Aleta vertical: sale del borde de la ventana; HSA = arctan(ancho/profundidad).
            ax.plot([edge_x, edge_x], [py0, py0 + fin], color=_WALL, lw=4,
                    solid_capstyle="round", zorder=5)
            far = window_w - edge_x                  # borde opuesto de la ventana
            hsa = np.degrees(np.arctan(window_w / fin))
            ax.plot([edge_x, far], [py0 + fin, py0], color=_ANG, lw=1.3, ls="--", zorder=5)
            line_ang = np.degrees(np.arctan2(-fin, far - edge_x)) % 360
            _angle_arc(ax, (edge_x, py0 + fin), *sorted((line_ang, 270.0)), radius=0.4 * fin,
                       label=f"HSA aleta\n{hsa:.0f}° {lbl}", lab_r=1.9)
        elif depth > 0 and ext > 0:                  # sólo alero con extensión
            hsa = np.degrees(np.arctan(ext / depth))
            ax.plot([edge_x, edge_x + sign * ext], [py0, py0 + depth], color=_ANG, lw=1.4, ls="--", zorder=5)
            line_ang = np.degrees(np.arctan2(depth, sign * ext))
            _angle_arc(ax, (edge_x, py0), *sorted((line_ang, 90.0)), radius=0.36 * depth,
                       label=f"HSA {hsa:.0f}° {lbl}", lab_r=1.7)

    ax.text(window_w / 2, top_y + 0.22, "Planta (HSA)", fontsize=9, ha="center", va="center", color="#444")


def _seccion(ax, depth, window_h, top, shadow_y, lit, sx0):
    """Vista de perfil (izq. del alzado), con la pared a la derecha y el VSA de corte."""
    # Pared (vertical) y ventana en x=sx0; alero sale hacia la izquierda.
    ax.plot([sx0, sx0], [-0.15, top + 0.1], color=_WALL, lw=2.5, zorder=3)
    if not lit:
        ax.plot([sx0, sx0], [0, window_h], color=_NOSUN, lw=6, solid_capstyle="butt", zorder=4)
    else:
        ax.plot([sx0, sx0], [shadow_y, window_h], color=_SHADE, lw=6, solid_capstyle="butt", zorder=4)
        ax.plot([sx0, sx0], [0, shadow_y], color=_SUN, lw=6, solid_capstyle="butt", zorder=4)
    if depth > 0:
        ax.plot([sx0, sx0 - depth], [top, top], color=_WALL, lw=4, solid_capstyle="round", zorder=4)
        # VSA de corte: del borde del alero al antepecho.
        vsa_cut = np.degrees(np.arctan(top / depth))
        ax.plot([sx0 - depth, sx0], [top, 0.0], color=_ANG, lw=1.4, ls="--", zorder=5)
        _angle_arc(ax, (sx0 - depth, top), -vsa_cut, 0.0, 0.36 * depth, f"VSA {vsa_cut:.0f}°", lab_r=1.7)
        # Cota de profundidad (horizontal).
        yd = top + 0.14
        ax.annotate("", (sx0 - depth, yd), (sx0, yd), arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))
        ax.text(sx0 - depth / 2, yd + 0.02, f"prof. {depth:.2f}", fontsize=6.5, color="#666", ha="center", va="bottom")
    ax.text(sx0 - depth / 2, -0.42, "Sección (perfil)", fontsize=9, ha="center", va="center", color="#444")
