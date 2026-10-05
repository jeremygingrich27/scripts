#!/usr/bin/env python3
"""plot_adatom_sites.py — scatter the adatom positions found under a directory.

    python3 plot_adatom_sites.py [DIR]        (default: the current directory)

Walks DIR for scf.in files, takes the highest-z atom in each as the adatom, and
scatters those x, y positions over the slab's top layer so the placements can be
checked by eye. Writes DIR/adatom_sites.png.

A file whose top plane holds more than one atom has no adatom (the bare slab
template, for instance) and is skipped.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qe_input as qi
import make_deposition as md

COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7"]   # as in plot_convergence.py
INK = "#444444"


def adatom_of(path):
    """(cell, adatom x/y in Angstrom, slab atoms) for one input, or None."""
    text = qi.read_input(path)
    a, b, c = md.check_cell(qi.get_cell(text))
    _unit, atoms = md.get_atoms(text)
    ztop, top = md.top_layer(atoms, c)
    if len(top) != 1:                      # no lone atom on top: no adatom
        return None
    adatom = top[0]
    slab = [at for at in atoms if at is not adatom]
    return (a, b, c), (adatom[1][0] * a, adatom[1][1] * b), slab


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    points, cell, slab = [], None, None
    for dirpath, _dirs, files in os.walk(root):
        if "scf.in" not in files:
            continue
        found = adatom_of(os.path.join(dirpath, "scf.in"))
        if found is None:
            continue
        cell, xy, slab = found
        points.append(xy)

    if not points:
        sys.exit(f"plot_adatom_sites: no adatom cases found under {root}")

    a, b, c = cell
    _ztop, top = md.top_layer(slab, c)
    species = sorted({at[0] for at in top})

    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    for lab, color in zip(species, COLORS):
        xs = [at[1][0] * a for at in top if at[0] == lab]
        ys = [at[1][1] * b for at in top if at[0] == lab]
        ax.scatter(xs, ys, s=260, color=color, alpha=0.5, label=f"{lab} (top layer)")
    ax.scatter([p[0] for p in points], [p[1] for p in points],
               s=28, color=COLORS[2], edgecolor=INK, linewidth=0.5, zorder=3,
               label=f"adatom ({len(points)} cases)")

    ax.plot([0, a, a, 0, 0], [0, 0, b, b, 0], color=INK, linewidth=0.8)
    ax.set_xlabel("x (Å)")
    ax.set_ylabel("y (Å)")
    ax.set_aspect("equal")
    ax.grid(color="#e6e6e6", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()

    out = os.path.join(root, "adatom_sites.png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"{len(points)} adatom positions from {root} -> {out}")


if __name__ == "__main__":
    main()
