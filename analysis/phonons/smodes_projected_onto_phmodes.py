#!/usr/bin/env python3
"""smodes_projected_onto_phmodes.py — Project Symmetry Modes onto Phonon Modes

Computes the projection of symmetry modes (from SMODES) onto phonon modes
(from VASP/phonon_extractor.py) using the formula::

    P = S^T @ Ph

where:
  - S  (smode_matrix)  has shape (n_components, n_sym_modes)
  - Ph (phmode_matrix) has shape (n_components, n_ph_modes)
  - P  (projection)    has shape (n_sym_modes,  n_ph_modes)

Each element P[i, j] gives the projection of symmetry mode i onto phonon mode j.
Rows of the output are symmetry modes; columns are phonon modes.

Usage
-----
::

    python smodes_projected_onto_phmodes.py \\
        SMODE_CSV PHMODE_CSV \\
        [--threshold T] [--top N] [--output FILE]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

import numpy as np


# ---------------------------------------------------------------------------
# Named constant for CSV quoting
# ---------------------------------------------------------------------------

import csv as _csv
QUOTE_ALL = _csv.QUOTE_ALL


# ---------------------------------------------------------------------------
# Label cleaning
# ---------------------------------------------------------------------------

_bracket_re = re.compile(r"\[([^\]]+)\]")


def _normalize_brackets(match: re.Match) -> str:
    inner = match.group(1)
    inner = re.sub(r"\s+", ";", inner.strip())
    return f"[{inner}]"


def clean_label(label: str) -> str:
    """Normalize mode labels to avoid CSV column-splitting issues.

    - Collapses repeated whitespace/tabs.
    - Replaces whitespace inside square brackets with semicolons,
      e.g. ``[0 0 0]`` -> ``[0;0;0]``.

    Args:
        label: Raw mode label string.

    Returns:
        Cleaned label string.
    """
    if not isinstance(label, str):
        return str(label)
    label = label.replace("\t", " ")
    label = " ".join(label.split())
    label = _bracket_re.sub(_normalize_brackets, label)
    return label


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def sniff_dialect(path: str) -> type:
    """Detect CSV dialect (comma vs tab, etc.); fall back to comma.

    Args:
        path: Path to the CSV file.

    Returns:
        A csv.Dialect (sub)class.
    """
    with open(path, newline="") as f:
        sample = f.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";"])
    except csv.Error:
        class _Default(csv.excel):
            delimiter = ","
        return _Default


def read_csv_with_labels(
    filename: str,
) -> tuple[np.ndarray | None, list[str] | None, list[str] | None]:
    """Read a CSV matrix with row and column labels.

    The first row is the header (corner cell + column labels).
    The first column of each subsequent row is the row label.

    Args:
        filename: Path to the CSV file.

    Returns:
        ``(data_matrix, row_labels, column_labels)`` where ``data_matrix``
        has shape ``(n_rows, n_columns)``, or ``(None, None, None)`` on error.
    """
    try:
        dialect = sniff_dialect(filename)
        with open(filename, newline="") as f:
            reader = csv.reader(f, dialect)
            first_row = next(reader)
            column_labels = [clean_label(x) for x in first_row[1:]]

            row_labels: list[str] = []
            data_rows: list[list[float]] = []

            for row in reader:
                if not row:
                    continue
                row_labels.append(row[0])
                try:
                    data_rows.append([float(x) for x in row[1:]])
                except ValueError as exc:
                    raise ValueError(
                        f"Non-numeric data in '{filename}' on row starting with "
                        f"'{row[0]}': {exc}"
                    )

        data_matrix = np.array(data_rows, dtype=float)
        return data_matrix, row_labels, column_labels
    except Exception as exc:
        print(f"[FAIL] Error reading '{filename}': {exc}")
        return None, None, None


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------

def calculate_projection(
    smode_matrix: np.ndarray,
    phmode_matrix: np.ndarray,
    sym_col_labels: list[str],
    ph_col_labels: list[str],
) -> tuple[np.ndarray | None, list[str] | None, list[str] | None]:
    """Compute the projection P = S^T @ Ph.

    The matrices must share the same number of displacement components
    (rows).  The output P[i, j] is the dot product of symmetry mode i
    with phonon mode j.

    Args:
        smode_matrix:  Shape (n_components, n_sym_modes).
        phmode_matrix: Shape (n_components, n_ph_modes).
        sym_col_labels: Column labels of S (symmetry mode names).
        ph_col_labels:  Column labels of Ph (phonon mode names).

    Returns:
        ``(P, sym_mode_names, ph_mode_names)`` where P has shape
        ``(n_sym_modes, n_ph_modes)``, or ``(None, None, None)`` on error.
    """
    print("\nCalculating projection (P = S^T @ Ph) ...")
    print(f"  Symmetry matrix S  : {smode_matrix.shape}  (components x sym_modes)")
    print(f"  Phonon   matrix Ph : {phmode_matrix.shape}  (components x ph_modes)")

    if smode_matrix.shape[0] != phmode_matrix.shape[0]:
        print(
            f"[FAIL] Row count mismatch: S has {smode_matrix.shape[0]} rows, "
            f"Ph has {phmode_matrix.shape[0]}."
        )
        return None, None, None

    # P = S^T @ Ph  ->  shape (n_sym_modes, n_ph_modes)
    projection = smode_matrix.T @ phmode_matrix

    sym_mode_names = [clean_label(x) for x in sym_col_labels]
    ph_mode_names = [clean_label(x) for x in ph_col_labels]

    print(f"  Projection P shape : {projection.shape}  (sym_modes x ph_modes)")
    return projection, sym_mode_names, ph_mode_names


# ---------------------------------------------------------------------------
# Output & analysis
# ---------------------------------------------------------------------------

def write_projection_csv(
    projection: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    output_filename: str,
    decimals: int = 6,
) -> str | None:
    """Write the projection matrix to a CSV file.

    Args:
        projection: 2-D numpy array (sym_modes x ph_modes).
        row_labels: Symmetry mode names (rows).
        col_labels: Phonon mode names (columns).
        output_filename: Path for the output CSV.
        decimals: Number of decimal places (default: 6).

    Returns:
        Output filename on success, ``None`` on failure.
    """
    try:
        with open(output_filename, "w", newline="") as f:
            writer = csv.writer(f, quoting=QUOTE_ALL)
            writer.writerow(["Symmetry_Mode"] + col_labels)
            for i, row_label in enumerate(row_labels):
                row_data = [row_label] + [f"{v:.{decimals}f}" for v in projection[i]]
                writer.writerow(row_data)
        print(f"[OK] Projection matrix written to: {output_filename}")
        return output_filename
    except OSError as exc:
        print(f"[FAIL] Cannot write projection file: {exc}")
        return None


def analyze_projections(
    projection: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    threshold: float = 0.1,
    top_n: int = 10,
) -> list[tuple[str, str, float, float]]:
    """Report the strongest projections above threshold.

    Args:
        projection: 2-D projection matrix (sym_modes x ph_modes).
        row_labels: Symmetry mode names.
        col_labels: Phonon mode names.
        threshold: Minimum |value| to include (default: 0.1).
        top_n: Number of top projections to display (default: 10).

    Returns:
        List of ``(sym_mode, ph_mode, value, abs_value)`` tuples sorted by
        descending absolute value.
    """
    significant: list[tuple[str, str, float, float]] = []
    for i, sym in enumerate(row_labels):
        for j, ph in enumerate(col_labels):
            v = float(projection[i, j])
            if abs(v) >= threshold:
                significant.append((sym, ph, v, abs(v)))

    significant.sort(key=lambda x: x[3], reverse=True)

    print(f"\nAnalysing projections (threshold = {threshold}) ...")
    print(f"Found {len(significant)} significant projection(s).")
    print(f"\nTop {min(top_n, len(significant))} strongest projections:")
    print("Symmetry Mode -> Phonon Mode : Projection Value")
    print("-" * 60)
    for sym, ph, v, _ in significant[:top_n]:
        print(f"  {sym} -> {ph} : {v:.6f}")

    return significant


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Project symmetry modes onto phonon modes (P = S^T @ Ph).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "smode_file",
        help="CSV file containing the symmetry-mode displacement matrix (S).",
    )
    p.add_argument(
        "phmode_file",
        help="CSV file containing the phonon-mode displacement matrix (Ph).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        metavar="T",
        help="Minimum |projection| to report (default: 0.1).",
    )
    p.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of top projections to display (default: 10).",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output CSV filename (default: <smode_stem>_projection.csv).",
    )
    return p


def main() -> None:
    """Entry point for smodes_projected_onto_phmodes.py."""
    args = build_parser().parse_args()

    if args.threshold < 0:
        sys.exit("[FAIL] --threshold must be >= 0.")
    if args.top <= 0:
        sys.exit("[FAIL] --top must be a positive integer.")

    for fp in (args.smode_file, args.phmode_file):
        if not os.path.exists(fp):
            sys.exit(f"[FAIL] File not found: '{fp}'")

    print(f"Symmetry modes file : {args.smode_file}")
    print(f"Phonon   modes file : {args.phmode_file}")

    print("\nReading symmetry modes (S) ...")
    smode_matrix, S_row_labels, S_col_labels = read_csv_with_labels(args.smode_file)
    if smode_matrix is None:
        sys.exit("[FAIL] Could not read symmetry modes file.")

    print("\nReading phonon modes (Ph) ...")
    phmode_matrix, Ph_row_labels, Ph_col_labels = read_csv_with_labels(args.phmode_file)
    if phmode_matrix is None:
        sys.exit("[FAIL] Could not read phonon modes file.")

    print(
        f"\n  S  : {smode_matrix.shape}  "
        f"({len(S_row_labels)} components x {len(S_col_labels)} sym modes)"
    )
    print(
        f"  Ph : {phmode_matrix.shape}  "
        f"({len(Ph_row_labels)} components x {len(Ph_col_labels)} ph modes)"
    )

    # P = S^T @ Ph   (sym_modes x ph_modes)
    P, sym_names, ph_names = calculate_projection(
        smode_matrix, phmode_matrix, S_col_labels, Ph_col_labels
    )
    if P is None:
        sys.exit("[FAIL] Projection calculation failed.")

    output_file = args.output or (
        os.path.splitext(args.smode_file)[0] + "_projection.csv"
    )
    proj_file = write_projection_csv(P, sym_names, ph_names, output_file)

    if proj_file:
        analyze_projections(
            P, sym_names, ph_names,
            threshold=args.threshold,
            top_n=args.top,
        )
        print(f"\n[OK] Processing complete.")
        print(f"     Projection matrix saved to: {proj_file}")
        print(f"     Dimensions: {len(sym_names)} sym modes x {len(ph_names)} ph modes")


if __name__ == "__main__":
    main()
