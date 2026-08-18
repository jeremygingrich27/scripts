#!/usr/bin/env python3
"""load_npy_files.py — Load and Display NumPy .npy Files

Loads one or more ``.npy`` files, prints each array's shape and dtype, and
reports basic statistics.  Useful for quick inspection of NumPy binary files
produced by VASP post-processing or phonon analysis workflows.

Usage
-----
::

    python load_npy_files.py FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def load_npy_files(
    file_paths: list[str],
) -> dict[str, np.ndarray]:
    """Load a list of ``.npy`` files and return a name-to-array mapping.

    The variable name for each file is derived from the file stem (filename
    without extension), preserving element symbols like ``Ca``, ``Mo``, etc.

    Args:
        file_paths: List of paths to ``.npy`` files.

    Returns:
        Dict mapping file-stem strings to loaded numpy arrays.  Files that
        fail to load are skipped with a warning.
    """
    variables: dict[str, np.ndarray] = {}

    for fp in file_paths:
        path = Path(fp)

        if not path.exists():
            print(f"[WARN] File not found: {fp} — skipping.")
            continue

        # Use Path.stem to get the name without extension, avoiding
        # fragile string splitting that fails on paths with dots in dirs
        variable_name = path.stem

        try:
            data = np.load(path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"[WARN] Cannot load '{fp}': {exc} — skipping.")
            continue

        variables[variable_name] = data
        print(f"[OK] Loaded '{variable_name}' from '{fp}'  shape={data.shape}  dtype={data.dtype}")

    return variables


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for load_npy_files.py."""
    p = argparse.ArgumentParser(
        description="Load and display .npy files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "files",
        nargs="+",
        help="Paths to .npy files to load.",
    )
    return p


def main() -> None:
    """Entry point for load_npy_files.py."""
    args = build_parser().parse_args()
    variables = load_npy_files(args.files)

    if not variables:
        sys.exit("[FAIL] No arrays loaded.")

    print(f"\n[OK] Loaded {len(variables)} array(s):")
    for name, arr in variables.items():
        if np.iscomplexobj(arr):
            print(f"  {name}: shape={arr.shape}, dtype={arr.dtype} (complex)")
        else:
            print(f"  {name}: shape={arr.shape}, dtype={arr.dtype}, "
                  f"min={arr.min():.6g}, max={arr.max():.6g}")


if __name__ == "__main__":
    main()
