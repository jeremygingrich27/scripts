#!/usr/bin/env python3
"""Tetrahedron bond-angle/length convergence from convergence_data/ files.

Implements the pseudocode signed off 2026-07-10. Run from the directory whose
direct children are the system dirs:

    plot_tetrahedra SYS1 [SYS2 ...] --center Si [--neighbor C] [--nn 4]
                    [--angle-crit 0.1] [--length-crit 0.001]

For every sweep case it rebuilds the cell from a b c alpha beta gamma, converts
the fractional positions to Cartesian, finds each center atom's nn nearest
neighbors of the other (or given) species over the 27 periodic images, splits
the bonds into 1 axial (max |c-component|) + basal, and reports per tetrahedron
the trio means: axial angle, basal angle, basal length, plus the unique axial
length. Angle classification is 4-fold specific: nn != 4 refuses to run.

Per system and sweep, 4 figures (axial_angle, basal_angle, axial_len,
basal_len), one curve per center atom, y = absolute deviation from that
system's densest case, error bars spanning each trio's min..max (none on
axial_len), dashed criterion lines at +/-angle-crit (deg) / +/-length-crit
(Ang). Saved to <cwd>/figures/<sweep>_<qty>__<SYS>.png.
"""

import argparse
import math
import sys
from itertools import combinations, product
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# dataviz categorical slots 1-6, fixed order
COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
GAP_FACTOR = 1.2  # (nn+1)-th neighbor must be this much beyond the nn-th

SWEEPS = [("ecut", "ecutwfc (Ry)", ["ecut"]),
          ("kmesh", "k-mesh", ["nk1", "nk2", "nk3"])]


def load_table(path):
    lines = path.read_text().splitlines()
    cols = lines[0].lstrip("#").split()
    rows = [dict(zip(cols, l.split())) for l in lines[1:] if l.strip()]
    return [r for r in rows if "N/A" not in r.values()]


def cell_matrix(a, b, c, alpha, beta, gamma):
    """Rows are the cell vectors; standard construction (v1 along x)."""
    ca, cb, cg = (math.cos(math.radians(x)) for x in (alpha, beta, gamma))
    sg = math.sin(math.radians(gamma))
    v1 = (a, 0.0, 0.0)
    v2 = (b * cg, b * sg, 0.0)
    cx = c * cb
    cy = c * (ca - cb * cg) / sg
    v3 = (cx, cy, math.sqrt(max(c * c - cx * cx - cy * cy, 0.0)))
    return (v1, v2, v3)


def to_cart(m, f):
    return tuple(sum(f[k] * m[k][i] for k in range(3)) for i in range(3))


def norm(v):
    return math.sqrt(sum(x * x for x in v))


def angle_deg(u, v):
    cosang = sum(a * b for a, b in zip(u, v)) / (norm(u) * norm(v))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosang))))


def tetrahedra(cell, atoms, center_sym, neighbor_sym, nn, where):
    """{'Si7': {qty: (mean, lo, hi)}} for each center atom in one case.

    atoms: list of (idx, symbol, fx, fy, fz). Bond search runs over the 27
    periodic images of every neighbor-species atom (pseudocode 9-10).
    """
    c_hat = cell[2]
    c_hat = tuple(x / norm(c_hat) for x in c_hat)
    out = {}
    for idx, sym, *f in atoms:
        if sym != center_sym:
            continue
        bonds = []
        for _, nsym, *g in atoms:
            if nsym == center_sym or (neighbor_sym and nsym != neighbor_sym):
                continue
            for shift in product((-1, 0, 1), repeat=3):
                d = tuple(g[k] + shift[k] - f[k] for k in range(3))
                bonds.append(to_cart(cell, d))
        bonds.sort(key=norm)
        if len(bonds) > nn and norm(bonds[nn]) < GAP_FACTOR * norm(bonds[nn - 1]):
            print(f"  warning: {where}: {sym}{idx} coordination shell not "
                  f"clean (d{nn+1}/d{nn} = {norm(bonds[nn])/norm(bonds[nn-1]):.2f})")
        shell = bonds[:nn]

        axial = max(shell, key=lambda v: abs(sum(x * y for x, y in zip(v, c_hat))))
        basal = [v for v in shell if v is not axial]
        ax_family = [angle_deg(axial, v) for v in basal]
        ba_family = [angle_deg(u, v) for u, v in combinations(basal, 2)]
        ba_lens = [norm(v) for v in basal]
        trio = lambda vals: (sum(vals) / len(vals), min(vals), max(vals))
        out[f"{sym}{idx}"] = {
            "axial_angle": trio(ax_family),
            "basal_angle": trio(ba_family),
            "axial_len": (norm(axial),) * 3,   # unique bond: zero spread
            "basal_len": trio(ba_lens),
        }
    return out


#             key            criterion-kind   y-axis label
QUANTITIES = [("axial_angle", "angle",  "axial angle, deviation from densest case (deg)"),
              ("basal_angle", "angle",  "basal angle, deviation from densest case (deg)"),
              ("axial_len",   "length", "axial bond length, deviation (Ang)"),
              ("basal_len",   "length", "basal bond length, deviation (Ang)")]


def draw(sweep, xlabel, sys_name, xs, labels, series, qty, ylabel, crit, out):
    """series: {center: list of (mean, lo, hi) per case}."""
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    for (center, vals), color in zip(series.items(), COLORS):
        ref = vals[-1][0]  # densest-case mean (pseudocode 15)
        y = [m - ref for m, _, _ in vals]
        lo = [ym - (l - ref) for ym, (_, l, _) in zip(y, vals)]
        hi = [(h - ref) - ym for ym, (_, _, h) in zip(y, vals)]
        ax.errorbar(xs, y, yerr=(lo, hi), fmt="-o", color=color,
                    linewidth=1.8, markersize=4, capsize=2, label=center)
    if labels is not None:
        ax.set_xticks(xs)
        ax.set_xticklabels(labels)
    ax.axhline(0, color="#bbbbbb", linewidth=0.8)
    for s in (+1, -1):
        ax.axhline(s * crit, color="#444444", linewidth=0.9, linestyle="--")
    ylo, yhi = ax.get_ylim()
    ax.set_ylim(min(ylo, -1.4 * crit), max(yhi, 1.4 * crit))
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(sys_name, fontsize=10)
    ax.grid(color="#e6e6e6", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")


def run_system(cwd, name, args, fig_dir):
    data_dir = cwd / name / "convergence_data"
    for sweep, xlabel, param_cols in SWEEPS:
        conv = data_dir / f"{sweep}_convergence.dat"
        pos = data_dir / f"{sweep}_positions.dat"
        rows = load_table(conv) if conv.exists() else []
        if len(rows) < 2 or not pos.exists():
            print(f"  warning: {name} has no usable {sweep} data, skipping")
            continue
        pos_rows = load_table(pos)

        cases = {}  # center -> list over cases of per-quantity trios
        xs, labels = [], ([] if sweep == "kmesh" else None)
        for i, row in enumerate(rows):
            key = tuple(row[c] for c in param_cols)
            atoms = [(int(p["idx"]), p["symbol"],
                      float(p["x"]), float(p["y"]), float(p["z"]))
                     for p in pos_rows
                     if tuple(p[c] for c in param_cols) == key]
            if not atoms:
                print(f"  warning: {name} {sweep} {key}: no positions, skipping case")
                continue
            cell = cell_matrix(*(float(row[c]) for c in
                                 ("a", "b", "c", "alpha", "beta", "gamma")))
            where = f"{name} {sweep} {'x'.join(key)}"
            tets = tetrahedra(cell, atoms, args.center, args.neighbor,
                              args.nn, where)
            if not tets:
                sys.exit(f"error: no {args.center} atoms found in {name}")
            for center, quantities in tets.items():
                cases.setdefault(center, []).append(quantities)
            if sweep == "ecut":
                xs.append(float(row["ecut"]))
            else:
                xs.append(len(xs))
                labels.append("x".join(key))

        for qty, kind, ylabel in QUANTITIES:
            crit = args.angle_crit if kind == "angle" else args.length_crit
            series = {c: [q[qty] for q in case_list]
                      for c, case_list in cases.items()}
            draw(sweep, xlabel, name, xs, labels, series, qty, ylabel, crit,
                 fig_dir / f"{sweep}_{qty}__{name}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+")
    ap.add_argument("--center", required=True, help="center species, e.g. Si")
    ap.add_argument("--neighbor", default=None,
                    help="neighbor species (default: any species != center)")
    ap.add_argument("--nn", type=int, default=4)
    ap.add_argument("--angle-crit", type=float, default=0.1, help="deg")
    ap.add_argument("--length-crit", type=float, default=0.001, help="Ang")
    args = ap.parse_args()

    if args.nn != 4:
        sys.exit("error: axial/basal angle classification is only defined "
                 "for nn=4; other coordinations not implemented")

    cwd = Path.cwd()
    for name in args.systems:
        if not (cwd / name / "convergence_data").is_dir():
            sys.exit(f"error: no {name}/convergence_data/ under {cwd}")
    fig_dir = cwd / "figures"
    fig_dir.mkdir(exist_ok=True)

    for name in args.systems:
        run_system(cwd, name, args, fig_dir)


if __name__ == "__main__":
    main()
