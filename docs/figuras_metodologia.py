"""Genera las figuras de `docs/metodologia-sombra.md` (estereográfica, numpy + matplotlib).

Reproducible:  uv run python docs/figuras_metodologia.py
Escribe los PNG en docs/assets/. Sólo numpy + matplotlib (Agg); reutiliza la geometría de
`solar.shading` y la proyección de `charts.sunpath`.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # raíz del repo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from charts.sunpath import _elev_to_r
from solar.shading import (
    fin_full_shade_hsa,
    full_shade_boundary,
    full_shade_boundary_analytic,
    overhang_full_shade_vsa,
    shaded_fraction,
)

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
WALL = 180.0                      # ventana al Sur (abajo en la carta)
W, H = 1.2, 1.5                   # ancho, alto de la ventana de ejemplo

C_SHADE = "#27c2d6"
C_VSA = "#c0392b"
C_LAT = "#e8833a"
C_RATIO = "#1696a8"
C_FIN = "#7d3c98"
C_REF = "#9aa7b4"


def _project(elev_deg, gamma_deg):
    """(elevación, HSA) → (x, y) en el plano estereográfico, Norte arriba."""
    a = np.radians(WALL + np.asarray(gamma_deg, dtype=float))
    r = _elev_to_r(np.asarray(elev_deg, dtype=float))
    return r * np.sin(a), r * np.cos(a)


def _frame(ax, title):
    """Dibuja el marco estereográfico: horizonte, mallas de elevación, cardinales."""
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(th), np.sin(th), color="#5b6770", lw=1.2)  # horizonte (r=1)
    for e in (10, 30, 50, 70):
        r = float(_elev_to_r(e))
        ax.plot(r * np.cos(th), r * np.sin(th), color=C_REF, lw=0.5, ls=":")
        ax.text(0, r, f"{e}°", color=C_REF, fontsize=6, ha="center", va="bottom")
    for ang, lab in ((90, "N"), (0, "E"), (270, "S"), (180, "W")):
        ar = np.radians(ang)
        ax.text(1.07 * np.cos(ar), 1.07 * np.sin(ar), lab, ha="center", va="center",
                fontsize=9, color="#444")
    ax.plot([0], [0], "+", color=C_REF, ms=7)
    ax.text(0, -0.06, "cenit", color=C_REF, fontsize=6, ha="center", va="top")
    ax.set_aspect("equal")
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.axis("off")
    ax.set_title(title, fontsize=11)


def _fit_circle(x, y):
    """Ajusta un círculo (mínimos cuadrados); devuelve (cx, cy, R, residual equidistancia)."""
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    c, *_ = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)
    cx, cy = c[0], c[1]
    R = np.sqrt(c[2] + cx ** 2 + cy ** 2)
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    return cx, cy, R, float(d.max() - d.min())


def _fill_full_shade(ax, cfg, n=41):
    """Pinta la región de sombra 100% real (fuerza bruta: shaded_fraction≥0.999) — ground truth."""
    g = np.linspace(-89, 89, 221)
    el = np.linspace(0.5, 89.5, 221)
    GG, EL = np.meshgrid(g, el)
    frac = shaded_fraction(WALL + GG, EL, WALL, cfg.get("depth", 0.6), W, H,
                           cfg.get("offset", 0.0), cfg.get("ext_left", 0.0), cfg.get("ext_right", 0.0),
                           cfg.get("fin_left", 0.0), cfg.get("fin_right", 0.0), cfg.get("ext_top", 0.0), n=n)
    X, Y = _project(EL, GG)
    ax.contourf(X, Y, frac, levels=[0.999, 2.0], colors=[C_SHADE], alpha=0.20)


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(ASSETS, name), dpi=130)
    plt.close(fig)
    print("escrito", name)


def fig01_vsa_circle():
    """Alero: el locus de sombra 100% es un arco del círculo de VSA constante."""
    depth = 0.6
    g = np.linspace(-89, 89, 200)
    vsa = overhang_full_shade_vsa(depth, H)
    elev = np.degrees(np.arctan(np.tan(np.radians(vsa)) * np.cos(np.radians(g))))
    x, y = _project(elev, g)
    cx, cy, R, resid = _fit_circle(x, y)

    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    _frame(ax, f"Alero: borde 100% = círculo de VSA constante (VSA={vsa:.0f}°)")
    _fill_full_shade(ax, dict(depth=depth, ext_left=3.0, ext_right=3.0))   # región real (fuerza bruta)
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(cx + R * np.cos(th), cy + R * np.sin(th), color=C_VSA, lw=0.8, ls="--",
            label=f"círculo ajustado (residual {resid:.1e})")
    ax.plot(x, y, color=C_VSA, lw=2.4, label="locus VSA (sombra 100%)")
    ax.legend(loc="upper right", fontsize=7)
    _save(fig, "fig01_vsa_circle.png")


def fig02_fin_line_and_escape():
    """Aleta: corte HSA = recta radial; 'escape por encima' = círculo (tan e = k·sin γ)."""
    fin, ext_top = 0.5, 0.4
    hsa = fin_full_shade_hsa(fin, W)                  # corte HSA (recta radial)
    k = (H + ext_top) / W                             # escape: tan(elev)=k·sin γ
    g = np.linspace(2, 89, 200)
    elev = np.degrees(np.arctan(k * np.sin(np.radians(g))))
    x, y = _project(elev, g)
    cx, cy, R, resid = _fit_circle(x, y)

    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    _frame(ax, "Aleta: recta radial (HSA) + círculo de escape")
    # recta radial del corte HSA (a ambos lados)
    for sgn in (+1, -1):
        xr, yr = _project(np.array([0.0, 90.0]), np.array([sgn * hsa, sgn * hsa]))
        ax.plot([0, xr[0]], [0, yr[0]], color=C_FIN, lw=2.0,
                label=("HSA aleta = %.0f° (recta radial)" % hsa) if sgn == 1 else None)
    th = np.linspace(0, 2 * np.pi, 400)
    ax.plot(cx + R * np.cos(th), cy + R * np.sin(th), color=C_LAT, lw=0.8, ls="--",
            label=f"círculo ajustado (residual {resid:.1e})")
    ax.plot(x, y, color=C_LAT, lw=2.4, label="escape: tan(elev)=k·sin γ")
    ax.legend(loc="upper right", fontsize=7)
    _save(fig, "fig02_fin_line_and_escape.png")


def fig03_single_fin_region():
    """Aleta sola (sin alero): la región 100% es de BAJA elevación (intervalo inferior)."""
    fin, ext_top = 0.5, 0.6
    g = np.linspace(-89, 89, 241)
    el = np.linspace(0.5, 89.5, 241)
    GG, EL = np.meshgrid(g, el)
    frac = shaded_fraction(WALL + GG, EL, WALL, 0.0, W, H, 0.0, 0.0, 0.0, fin, fin, ext_top, n=41)
    X, Y = _project(EL, GG)

    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    _frame(ax, "Aleta sola (sin alero): sombra 100% a baja elevación")
    ax.contourf(X, Y, frac, levels=[0.999, 2.0], colors=[C_FIN], alpha=0.25)
    hsa = fin_full_shade_hsa(fin, W)
    for sgn in (+1, -1):
        xr, yr = _project(np.array([0.0, 90.0]), np.array([sgn * hsa, sgn * hsa]))
        ax.plot([0, xr[0]], [0, yr[0]], color=C_FIN, lw=1.6, ls="--")
    ax.text(*_project(8, 80), "100%", color=C_FIN, fontsize=9, ha="center")
    ax.text(0.0, -1.02, f"|γ| ≥ {hsa:.0f}° y elevación baja", color=C_FIN, fontsize=7, ha="center")
    _save(fig, "fig03_single_fin_region.png")


def fig04_eggcrate_composed():
    """Celosía: el borde 100% como ENVOLVENTE de las piezas analíticas (mínimo por γ)."""
    depth, offset = 0.6, 0.0
    fin, ext, ext_top = 0.5, 0.0, 0.4
    g = np.linspace(-89, 89, 361)
    a = np.radians(np.abs(g))
    top = H + offset
    # piezas candidatas
    vsa = overhang_full_shade_vsa(depth, H, offset)
    elev_vsa = np.degrees(np.arctan(np.tan(np.radians(vsa)) * np.cos(a)))
    with np.errstate(divide="ignore", invalid="ignore"):
        elev_esc = np.degrees(np.arctan((H + ext_top) * np.sin(a) / W))
        m = np.tan(a)
        elev_ratio = np.degrees(np.arctan(top * np.sin(a) * np.cos(a) / (fin * np.sin(a) + ext * np.cos(a))))
    g_full, elev_full = full_shade_boundary_analytic(WALL, depth, W, H, offset, ext, ext, fin, fin, ext_top)

    fig, ax = plt.subplots(figsize=(5.8, 5.8))
    _frame(ax, "Celosía: borde 100% = envolvente de arcos analíticos")
    _fill_full_shade(ax, dict(depth=depth, offset=offset, ext_left=ext, ext_right=ext,
                              fin_left=fin, fin_right=fin, ext_top=ext_top))   # región real
    for curve, col, lab in ((elev_vsa, C_VSA, "arco VSA (alero)"),
                            (elev_ratio, C_RATIO, "curva-razón (alero+aleta)"),
                            (elev_esc, C_LAT, "círculo de escape (aleta)")):
        xx, yy = _project(np.clip(curve, 0, 90), g)
        ax.plot(xx, yy, color=col, lw=0.9, ls="--", alpha=0.8, label=lab)
    hsa = fin_full_shade_hsa(fin, W)
    for sgn in (+1, -1):
        xr, yr = _project(np.array([0.0, 90.0]), np.array([sgn * hsa, sgn * hsa]))
        ax.plot([0, xr[0]], [0, yr[0]], color=C_FIN, lw=0.9, ls=":",
                label="ala: HSA aleta" if sgn == 1 else None)
    xb, yb = _project(elev_full, g_full)
    fin_mask = elev_full < 89.5
    ax.plot(xb[fin_mask], yb[fin_mask], color="#0d7a8a", lw=2.6, label="borde 100% (envolvente)")
    ax.legend(loc="upper right", fontsize=6.5)
    _save(fig, "fig04_eggcrate_composed.png")


def fig05_validation_overlay():
    """Validación: borde analítico (línea) sobre ray casting (puntos), config asimétrica."""
    args = (WALL, 0.5, W, H, 0.2, 0.2, 0.0, 0.3, 0.5, 0.3)
    g, e_ana = full_shade_boundary_analytic(*args)
    gr, e_ray = full_shade_boundary(*args)
    sig = (e_ray < 89.5) & (e_ray > 1.0)
    dmax = float(np.max(np.abs(e_ana - e_ray)[sig])) if sig.any() else 0.0

    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    _frame(ax, f"Validación: analítico vs ray casting (máx |Δ|={dmax:.3f}°)")
    xr, yr = _project(np.where(e_ray < 89.5, e_ray, np.nan), gr)
    ax.plot(xr, yr, "o", mfc="none", mec="#c0392b", ms=3.5, mew=0.7, label="ray casting")
    xa, ya = _project(np.where(e_ana < 89.5, e_ana, np.nan), g)
    ax.plot(xa, ya, color="#0d7a8a", lw=2.0, label="analítico (cerrado)")
    ax.legend(loc="upper right", fontsize=7)
    _save(fig, "fig05_validation_overlay.png")


def fig06_coverage_effect():
    """El efecto del umbral de cobertura: al subir hacia 100% el borde 'salta' SOLO en configs
    asimétricas con dispositivo débil (franja real); en las simétricas se mantiene suave."""
    from solar.shading import full_shade_boundary_analytic, practical_shade_boundary
    asim = (WALL, 0.6, W, H, 0.0, 0.195, 0.0, 0.0, 0.19, 0.4)   # ext izq + aleta somera der
    sim = (WALL, 0.6, W, H, 0.0, 0.0, 0.0, 0.5, 0.5, 0.4)       # celosía simétrica
    covs = [(0.99, "#7fbf7f"), (0.999, "#e8a13a"), (0.999999, "#1696a8")]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, args, title in ((axes[0], asim, "Asimétrica (aleta somera + ext. opuesta)"),
                            (axes[1], sim, "Simétrica")):
        for cov, col in covs:
            g, e = practical_shade_boundary(*args, coverage=cov)
            ax.plot(g, np.where(e < 89.5, e, np.nan), color=col, lw=1.8,
                    label=f"práctico {cov*100:.4f}%")
        g, e = full_shade_boundary_analytic(*args)
        ax.plot(g, np.where(e < 89.5, e, np.nan), color="#c0392b", lw=1.4, ls="--",
                label="100% estricto")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("HSA γ (°)")
        ax.set_ylabel("elevación de sombra (°)")
        ax.set_xlim(-50, 50)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7, loc="lower center")
    fig.suptitle("Efecto del umbral de cobertura sobre el borde (el salto es geometría real)",
                 fontsize=11)
    _save(fig, "fig06_coverage_effect.png")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    fig01_vsa_circle()
    fig02_fin_line_and_escape()
    fig03_single_fin_region()
    fig04_eggcrate_composed()
    fig05_validation_overlay()
    fig06_coverage_effect()


if __name__ == "__main__":
    main()
