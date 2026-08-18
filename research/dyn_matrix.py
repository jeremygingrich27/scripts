"""dyn_matrix.py — Convert NumPy .npy Files to Human-Readable Text

Loads every ``.npy`` file in a directory, prints its shape, and saves it
as a ``.txt`` file using ``numpy.savetxt``.  Real arrays are formatted as
plain floats; complex arrays use the ``a+bj`` notation.

The original ``.npy`` files are re-saved in-place (no data change, useful
for ensuring canonical serialisation format).

Usage
-----
::

    python dyn_matrix.py <directory>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def list_npy_files(directory: Path) -> list[Path]:
    """Return all ``.npy`` files in *directory* (non-recursive).

    Args:
        directory: Directory to scan.

    Returns:
        Sorted list of Path objects for each ``.npy`` file found.
    """
    return sorted(directory.glob("*.npy"))


def convert_npy_to_txt(npy_path: Path) -> Path:
    """Load a ``.npy`` file and write a human-readable ``.txt`` counterpart.

    For real arrays the format is ``%.6f``; for complex arrays each element
    is rendered as ``<real>+<imag>j`` (e.g. ``1.234567+0.000000j``).

    Args:
        npy_path: Path to the ``.npy`` file to convert.

    Returns:
        Path of the written ``.txt`` file.

    Raises:
        FileNotFoundError: If *npy_path* does not exist.
        ValueError: If the file cannot be loaded as a numpy array.
    """
    if not npy_path.exists():
        raise FileNotFoundError(f"File not found: {npy_path}")

    try:
        data = np.load(npy_path)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot load {npy_path}: {exc}") from exc

    txt_path = npy_path.with_suffix(".txt")
    print(f"  Shape of {npy_path.name}: {data.shape}")

    if np.iscomplexobj(data):
        print(f"  Complex data — saving in a+bj format")
        # Format each element as "<real>+<imag>j" regardless of dimensionality
        def _fmt(z: complex) -> str:
            sign = "+" if z.imag >= 0 else ""
            return f"{z.real:.6f}{sign}{z.imag:.6f}j"

        if data.ndim == 2:
            formatted = [[_fmt(z) for z in row] for row in data]
        elif data.ndim == 1:
            formatted = [_fmt(z) for z in data]
        else:
            # Flatten higher-dimensional complex arrays to 2-D for saving
            formatted = [[_fmt(z) for z in row] for row in data.reshape(-1, data.shape[-1])]

        np.savetxt(txt_path, formatted, fmt="%s", delimiter=" ",
                   header="Complex Numbers (a+bj format)")
    else:
        np.savetxt(txt_path, data, fmt="%.6f", delimiter=" ",
                   header="Real Numbers")

    print(f"  Converted -> {txt_path.name}")
    return txt_path


def resave_npy(npy_path: Path) -> None:
    """Re-serialise a ``.npy`` file in canonical format (no data change).

    Args:
        npy_path: Path to the ``.npy`` file.

    Raises:
        FileNotFoundError: If *npy_path* does not exist.
        ValueError: If the file cannot be loaded.
    """
    if not npy_path.exists():
        raise FileNotFoundError(f"File not found: {npy_path}")
    try:
        data = np.load(npy_path)
        np.save(npy_path, data)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot process {npy_path}: {exc}") from exc


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for dyn_matrix.py."""
    p = argparse.ArgumentParser(
        description="Convert .npy files in a directory to human-readable .txt files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "directory",
        type=Path,
        help="Directory containing .npy files to process.",
    )
    return p


def main() -> None:
    """Entry point for dyn_matrix.py."""
    args = build_parser().parse_args()
    directory: Path = args.directory.expanduser()

    if not directory.is_dir():
        sys.exit(f"[FAIL] '{directory}' is not a valid directory.")

    npy_files = list_npy_files(directory)
    if not npy_files:
        sys.exit(f"[FAIL] No .npy files found in '{directory}'.")

    print(f"Found {len(npy_files)} .npy file(s) in '{directory}'")

    for npy_path in npy_files:
        print(f"\nProcessing {npy_path.name}")
        try:
            resave_npy(npy_path)
            print(f"  [OK] Re-saved {npy_path.name}")
            convert_npy_to_txt(npy_path)
        except (FileNotFoundError, ValueError) as exc:
            print(f"  [FAIL] {exc}")

    print("\n[OK] Done.")


if __name__ == "__main__":
    main()
