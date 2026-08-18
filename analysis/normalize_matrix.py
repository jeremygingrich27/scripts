#!/usr/bin/env python3
"""normalize_matrix.py — Normalize Phonon Projection Vectors

Reads a CSV matrix of phonon projection vectors (rows = displacement
components, columns = phonon modes), normalises each column to unit L2
norm, saves the normalised matrix, and reports whether all column pairs
are orthogonal within a given tolerance.

Expected input format
----------------------
- First column: row index / label (string).
- Remaining columns: numeric values, one column per phonon mode.
- Header row: corner label + mode column names.

Example::

    ,Mode1,Mode2,Mode3
    atom1_dx,0.1,0.0,-0.2
    atom1_dy,0.0,0.5,0.0
    ...

Usage
-----
::

    python normalize_matrix.py --input phonon_projections.csv \\
        [--output normalised.csv] [--tolerance 1e-10]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Named constant instead of the magic number 1 (csv.QUOTE_ALL)
import csv
QUOTE_ALL = csv.QUOTE_ALL


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def normalize_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """Normalise every column of *df* to unit L2 norm.

    Args:
        df: DataFrame with numeric columns.

    Returns:
        New DataFrame of the same shape with unit-norm columns.

    Raises:
        ValueError: If any column has zero norm (would produce NaN).
    """
    norms = np.linalg.norm(df.values, axis=0)
    zero_cols = [col for col, n in zip(df.columns, norms) if n == 0]
    if zero_cols:
        raise ValueError(f"Zero-norm columns (cannot normalise): {zero_cols}")
    return df.apply(lambda col: col / np.linalg.norm(col.values), axis=0)


def check_orthogonality(
    normed: "pd.DataFrame",
    tolerance: float = 1e-10,
) -> bool:
    """Check pairwise orthogonality of columns in a normalised DataFrame.

    Args:
        normed: DataFrame whose columns are expected to be unit-norm vectors.
        tolerance: Dot-product threshold below which columns are considered
            orthogonal (default: 1e-10).

    Returns:
        ``True`` if all column pairs are orthogonal within tolerance,
        ``False`` otherwise.
    """
    cols = normed.columns
    n = len(cols)
    orthogonal = True

    for i in range(n):
        for j in range(i + 1, n):
            dot = float(np.dot(normed.iloc[:, i], normed.iloc[:, j]))
            if abs(dot) > tolerance:
                print(f"[WARN] Columns not orthogonal: '{cols[i]}' x '{cols[j]}' "
                      f"(dot = {dot:.3e})")
                orthogonal = False

    return orthogonal


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for normalize_matrix.py."""
    p = argparse.ArgumentParser(
        description="Normalise phonon projection vectors and check orthogonality.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--input",
        required=True,
        metavar="FILE",
        help="Input CSV file with phonon projection vectors.",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help=(
            "Output CSV file for the normalised matrix. "
            "Defaults to <input_stem>_normalized.csv."
        ),
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=1e-10,
        metavar="TOL",
        help="Dot-product orthogonality threshold (default: 1e-10).",
    )
    return p


def main() -> None:
    """Entry point for normalize_matrix.py."""
    args = build_parser().parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"[FAIL] Input file not found: {input_path}")

    if args.tolerance < 0:
        sys.exit("[FAIL] --tolerance must be >= 0.")

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = input_path.with_name(input_path.stem + "_normalized.csv")

    print(f"[INFO] Reading {input_path} ...")
    try:
        df = pd.read_csv(input_path, index_col=0)
    except Exception as exc:
        sys.exit(f"[FAIL] Cannot read CSV: {exc}")

    # Normalise columns
    print("[INFO] Normalising columns ...")
    try:
        normed = normalize_columns(df)
    except ValueError as exc:
        sys.exit(f"[FAIL] {exc}")

    # Write output — QUOTE_ALL ensures mode labels with spaces/commas are safe
    normed.to_csv(out_path, index=True, quoting=QUOTE_ALL)
    print(f"[OK]   Normalised matrix written to {out_path}")

    # Check orthogonality
    print(f"[INFO] Checking orthogonality (tolerance = {args.tolerance:.1e}) ...")
    if check_orthogonality(normed, tolerance=args.tolerance):
        print("[OK]   All columns are orthogonal within tolerance.")
    else:
        print("[WARN] Some column pairs are not orthogonal (see warnings above).")


if __name__ == "__main__":
    main()
