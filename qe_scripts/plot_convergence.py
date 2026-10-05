#!/usr/bin/env python3
"""Plot convergence figures from convergence_data/ tables.

Implements the pseudocode signed off 2026-07-10 (amended: energy deviation is
per formula unit, not per atom). Run from the directory whose direct children
are the system dirs:

    plot_convergence SYS1 [SYS2 ...] [--outdir DIR]

For each sweep type (ecut, kmesh) and each quantity (a, c, energy, scf_time)
one figure overlays the named systems, y = deviation from each system's
densest case (energy in meV/f.u., lattice in %; scf_time is raw seconds with
no reference). Criterion lines: +/-0.1 % (a, c), +/-1 meV/f.u. (energy), none
for scf_time. Figures land in <cwd>/figures/<sweep>_<qty>__SYS1__SYS2.png,
or in DIR (created if missing) with --outdir (amendment signed off 2026-10-03).

A named system without convergence_data/ is a hard error; a missing sweep
file (or one with < 2 usable rows) only warns and drops that system from that
sweep's figures. N/A rows are dropped.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RY_TO_MEV = 13605.693

#            key         column         mode      criterion   y-axis label
QUANTITIES = [
    ("a",        "a",            "pct",    0.1,  "a, deviation from densest case (%)"),
    ("c",        "c",            "pct",    0.1,  "c, deviation from densest case (%)"),
    ("energy",   "E_ry_per_fu",  "mev",    1.0,  "E, deviation from densest case (meV/f.u.)"),
    ("scf_time", "scf_cycle_s",  "raw",    None, "SCF cycle time (s)"),
]

SWEEPS = [("ecut", "ecutwfc (Ry)"), ("kmesh", "k-mesh")]

# dataviz categorical slots 1-4, fixed order (validated set, worst CVD dE 24.2)
COLORS = ["#2a78d6", "#1baf7a", "#eda100", "#4a3aa7"]
INK = "#444444"


def load_table(path):
    """convergence_data table -> list of {column: string}, N/A rows dropped."""
    lines = path.read_text().splitlines()
    cols = lines[0].lstrip("#").split()
    rows = [dict(zip(cols, l.split())) for l in lines[1:] if l.strip()]
    return [r for r in rows if "N/A" not in r.values()]


def sweep_x(rows, sweep):
    """x values (ecut: floats) or category labels (kmesh: '10x10x2')."""
    if sweep == "ecut":
        return [float(r["ecut"]) for r in rows]
    return [f'{r["nk1"]}x{r["nk2"]}x{r["nk3"]}' for r in rows]


def deviations(rows, column, mode):
    vals = [float(r[column]) for r in rows]
    ref = vals[-1]  # last row = densest case (tables are sorted by the harvester)
    if mode == "pct":
        return [(v - ref) / ref * 100 for v in vals]
    if mode == "mev":
        return [(v - ref) * RY_TO_MEV for v in vals]
    return vals  # raw


def draw_figure(sweep, xlabel, systems, data, qty, column, mode, crit, ylabel, out):
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    categorical = sweep == "kmesh"

    for (name, rows), color in zip(data.items(), COLORS):
        x = sweep_x(rows, sweep)
        y = deviations(rows, column, mode)
        if categorical:
            x = range(len(x))
        ax.plot(x, y, "-o", color=color, linewidth=1.8, markersize=5, label=name)

    if categorical:
        # ticks labeled by mesh; if systems' meshes differ, stack their labels
        n = max(len(rows) for rows in data.values())
        labels = []
        for i in range(n):
            here = {sweep_x(rows, sweep)[i] for rows in data.values() if i < len(rows)}
            labels.append("\n".join(sorted(here)))
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels)

    if crit is not None:
        ax.axhline(0, color="#bbbbbb", linewidth=0.8)
        for s in (+1, -1):
            ax.axhline(s * crit, color=INK, linewidth=0.9, linestyle="--")
        lo, hi = ax.get_ylim()
        ax.set_ylim(min(lo, -1.4 * crit), max(hi, 1.4 * crit))

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(color="#e6e6e6", linewidth=0.6)
    ax.set_axisbelow(True)
    if len(data) > 1:
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"  wrote {out}")


def main():
    args = sys.argv[1:]
    outdir = None
    if "--outdir" in args:
        i = args.index("--outdir")
        if i + 1 >= len(args):
            sys.exit("error: --outdir needs a directory")
        outdir = args[i + 1]
        del args[i:i + 2]
    systems = args
    if not systems:
        sys.exit("usage: plot_convergence SYS1 [SYS2 ...] [--outdir DIR]")

    cwd = Path.cwd()
    for name in systems:
        if not (cwd / name / "convergence_data").is_dir():
            sys.exit(f"error: no {name}/convergence_data/ under {cwd}")
    fig_dir = Path(outdir) if outdir else cwd / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    for sweep, xlabel in SWEEPS:
        data = {}  # system -> usable rows, insertion order = CLI order
        for name in systems:
            path = cwd / name / "convergence_data" / f"{sweep}_convergence.dat"
            rows = load_table(path) if path.exists() else []
            if len(rows) < 2:
                print(f"  warning: {name} has no usable {sweep} data, "
                      f"skipping it on {sweep} figures")
                continue
            data[name] = rows
        if not data:
            continue

        tag = "__".join(systems)
        for qty, column, mode, crit, ylabel in QUANTITIES:
            draw_figure(sweep, xlabel, systems, data, qty, column, mode, crit,
                        ylabel, fig_dir / f"{sweep}_{qty}__{tag}.png")


if __name__ == "__main__":
    main()
