#!/usr/bin/env python3
"""plot_phonon.py — Plot Phonon Band Structure

Reads a PHONON_BAND.dat file (VASPKIT format) and a KLABELS file, then
produces a phonon band-structure plot.

Expected file formats
----------------------
**PHONON_BAND.dat**::

    # Branch-Index: 1
    0.0  12.5
    0.1  13.2
    ...
    # Branch-Index: 2
    ...

Each ``# Branch-Index: N`` line starts a new branch.  Data lines contain
two whitespace-separated floats: k-path coordinate and frequency.

**KLABELS**::

    High-symmetry point labels
    GAMMA   0.0
    X       0.5
    M       1.0
    *       (lines starting with * are ignored)

Lines starting with ``*`` or blank lines are skipped.

Usage
-----
::

    python plot_phonon.py [-b BANDS] [-k KLABELS] [-o OUTPUT] [-t TITLE]
        [--figsize W H]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def read_high_symmetry_points(filename: str) -> list[tuple[str, float]]:
    """Read high-symmetry point labels and coordinates from a KLABELS file.

    Args:
        filename: Path to the KLABELS file.

    Returns:
        List of ``(label, coordinate)`` tuples in file order.

    Raises:
        FileNotFoundError: If *filename* does not exist.
    """
    if not Path(filename).exists():
        raise FileNotFoundError(f"KLABELS file not found: {filename}")

    labels: list[tuple[str, float]] = []
    with open(filename) as f:
        next(f, None)   # skip header line
        for line in f:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    coord = float(parts[1])
                    labels.append((parts[0], coord))
                except ValueError:
                    continue   # skip lines whose second column is not a number

    return labels


def read_branches(file_path: str) -> list[list[tuple[float, float]]]:
    """Read phonon branches from a PHONON_BAND.dat file.

    Each branch is delimited by a ``# Branch-Index: N`` header.  Lines that
    cannot be parsed as two floats are skipped with a warning rather than
    aborting the entire load.

    Args:
        file_path: Path to the PHONON_BAND.dat file.

    Returns:
        List of branches; each branch is a list of ``(k, frequency)`` tuples.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"Band file not found: {file_path}")

    branches: list[list[tuple[float, float]]] = []
    current_branch: list[tuple[float, float]] | None = None

    with open(file_path) as f:
        for lineno, line in enumerate(f, 1):
            if line.startswith("# Branch-Index:"):
                if current_branch is not None:
                    branches.append(current_branch)
                current_branch = []
            elif line.strip() and not line.startswith("#"):
                if current_branch is None:
                    continue   # data before any branch header — skip
                parts = line.split()
                if len(parts) < 2:
                    print(f"Warning: line {lineno} has fewer than 2 columns — skipping.")
                    continue
                try:
                    x, y = float(parts[0]), float(parts[1])
                    current_branch.append((x, y))
                except ValueError:
                    print(f"Warning: line {lineno} contains non-numeric data — skipping.")
                    continue

    if current_branch is not None:
        branches.append(current_branch)

    return branches


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot_combined(
    branches: list[list[tuple[float, float]]],
    high_symmetry_points: list[tuple[str, float]],
    output_file: str = "phonon_bands.png",
    title: str = "Phonon Band Structure",
    figsize: tuple[float, float] = (12, 6),
) -> None:
    """Generate and save the phonon band-structure plot.

    Args:
        branches: List of branches from :func:`read_branches`.
        high_symmetry_points: List of ``(label, coord)`` tuples.
        output_file: Path for the output PNG file.
        title: Plot title string.
        figsize: Figure dimensions ``(width, height)`` in inches.
    """
    fig, ax = plt.subplots(figsize=figsize)

    for branch in branches:
        if not branch:
            continue
        x_vals = [pt[0] for pt in branch]
        y_vals = [pt[1] for pt in branch]
        ax.plot(x_vals, y_vals, linewidth=1, color="C0")

    if high_symmetry_points:
        x_coords = [c for _, c in high_symmetry_points]
        x_labels = [lbl for lbl, _ in high_symmetry_points]
        for x in x_coords:
            ax.axvline(x, color="gray", linestyle="--", linewidth=0.5)
        ax.set_xticks(x_coords)
        ax.set_xticklabels(x_labels)
        if x_coords:
            ax.set_xlim(x_coords[0], x_coords[-1])

    ax.set_xlabel("K-Path")
    ax.set_ylabel("Frequency (meV)")
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[OK] Plot saved: {output_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for plot_phonon.py."""
    p = argparse.ArgumentParser(
        description="Plot phonon band structure from VASP/VASPKIT output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-b", "--bands", default="PHONON_BAND.dat",
                   help="Phonon bands file (default: PHONON_BAND.dat).")
    p.add_argument("-k", "--klabels", default="KLABELS",
                   help="K-point labels file (default: KLABELS).")
    p.add_argument("-o", "--output", default="phonon_bands.png",
                   help="Output image file (default: phonon_bands.png).")
    p.add_argument("-t", "--title", default="Phonon Band Structure",
                   help='Plot title (default: "Phonon Band Structure").')
    p.add_argument("--figsize", nargs=2, type=float, default=[12, 6],
                   metavar=("W", "H"),
                   help="Figure size in inches (default: 12 6).")
    return p


def main() -> None:
    """Entry point for plot_phonon.py."""
    args = build_parser().parse_args()

    try:
        branches = read_branches(args.bands)
    except FileNotFoundError as exc:
        sys.exit(f"[FAIL] {exc}")

    if not branches:
        sys.exit(f"[FAIL] No branches found in '{args.bands}'.")

    try:
        hs_points = read_high_symmetry_points(args.klabels)
    except FileNotFoundError as exc:
        sys.exit(f"[FAIL] {exc}")

    print(f"[OK] Read {len(branches)} branches from '{args.bands}'.")
    print(f"[OK] Read {len(hs_points)} high-symmetry points from '{args.klabels}'.")

    plot_combined(
        branches,
        hs_points,
        output_file=args.output,
        title=args.title,
        figsize=tuple(args.figsize),
    )


if __name__ == "__main__":
    main()
