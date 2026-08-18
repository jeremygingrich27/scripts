#!/usr/bin/env python3
"""octahedral_tilt.py — Apply Glazer Octahedral Tilts to a POSCAR

Applies a specified Glazer octahedral tilt pattern to the atomic coordinates
in a POSCAR file and writes the result to a new file.

Glazer notation
---------------
Each Glazer tilt type is written as a combination of superscript labels for
the three crystallographic axes::

    + (in-phase)    : tilt angle alternates with the SAME sense layer-to-layer
    - (out-of-phase): tilt angle alternates with OPPOSITE sense layer-to-layer
    0 (no tilt)     : no rotation about that axis

Displacement convention used here
-----------------------------------
Let ``coord`` be the fractional coordinate along the axis perpendicular to
the tilt axis, and ``layer_index`` be the integer layer number of an atom
along the tilt axis.

- In-phase  (+): ``displacement = amplitude * sin(2*pi*coord)``
- Out-of-phase (-): ``displacement = amplitude * sin(2*pi*coord) * (-1)**layer_index``

The ``layer_index`` is determined by binning fractional coordinates along
the tilt axis into discrete planes (resolution set by ``--layer-bins``).

Supported tilt types (all 15 Glazer classes)
---------------------------------------------
a+a+a+, a+a+a-, a+a-a+, a-a-a-,
a0a0a+, a0a0a-, a0b+b+, a0b+b-,
a0b-b-, a0a0b+, a0a0b-, a+a0c+,
a-a0c-, a+b+c+, a-b-c-

Usage
-----
::

    python octahedral_tilt.py [--poscar FILE] [--tilt TYPE] \\
        [--magnitude FLOAT] [--output FILE] [--layer-bins N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# POSCAR I/O
# ---------------------------------------------------------------------------

def read_poscar(
    filename: str,
) -> tuple[float, np.ndarray, list[str], list[int], np.ndarray]:
    """Parse a POSCAR file.

    Args:
        filename: Path to the POSCAR file.

    Returns:
        ``(scale, lattice_vectors, elements, num_atoms, coords)`` where:

        - ``scale``           – universal scaling factor (float).
        - ``lattice_vectors`` – 3x3 array.
        - ``elements``        – list of element symbol strings.
        - ``num_atoms``       – list of atom counts per species.
        - ``coords``          – Nx3 Cartesian coordinate array.

    Raises:
        FileNotFoundError: If *filename* does not exist.
        ValueError: If the file cannot be parsed as a valid POSCAR.
    """
    if not Path(filename).exists():
        raise FileNotFoundError(f"POSCAR file not found: {filename}")

    with open(filename) as f:
        lines = f.readlines()

    try:
        scale = float(lines[1].strip())
        lattice_vectors = np.array(
            [list(map(float, line.split())) for line in lines[2:5]]
        )
        elements = lines[5].split()
        num_atoms = list(map(int, lines[6].split()))
        total_atoms = sum(num_atoms)

        # Handle optional Selective dynamics line
        coord_start = 7
        if lines[7].strip()[0].lower() == "s":
            coord_start = 8

        coords = np.array(
            [list(map(float, lines[i].split()[:3]))
             for i in range(coord_start + 1, coord_start + 1 + total_atoms)]
        )
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Cannot parse POSCAR '{filename}': {exc}") from exc

    return scale, lattice_vectors, elements, num_atoms, coords


def write_poscar(
    filename: str,
    scale: float,
    lattice_vectors: np.ndarray,
    elements: list[str],
    num_atoms: list[int],
    coords: np.ndarray,
) -> None:
    """Write a POSCAR file with Cartesian coordinates.

    Args:
        filename: Output file path.
        scale: Universal scaling factor.
        lattice_vectors: 3x3 lattice vector array.
        elements: List of element symbol strings.
        num_atoms: List of per-species atom counts.
        coords: Nx3 Cartesian coordinate array.
    """
    with open(filename, "w") as f:
        f.write("Generated POSCAR with Octahedral Tilt\n")
        f.write(f"  {scale}\n")
        for vec in lattice_vectors:
            f.write("   " + "   ".join(f"{v:16.10f}" for v in vec) + "\n")
        f.write("   " + "   ".join(elements) + "\n")
        f.write("   " + "   ".join(map(str, num_atoms)) + "\n")
        f.write("Cartesian\n")
        for coord in coords:
            f.write("   " + "   ".join(f"{v:16.10f}" for v in coord) + "\n")


# ---------------------------------------------------------------------------
# Layer index helper
# ---------------------------------------------------------------------------

def compute_layer_indices(
    frac_coords: np.ndarray,
    axis: int,
    n_bins: int = 20,
) -> np.ndarray:
    """Assign a discrete layer index to each atom along *axis*.

    The fractional coordinates along *axis* are binned into *n_bins*
    equal intervals in [0, 1).  Atoms in the same bin get the same
    layer index.

    Args:
        frac_coords: Nx3 fractional coordinate array.
        axis: Axis index (0=a, 1=b, 2=c).
        n_bins: Number of discrete layers (default 20).

    Returns:
        1-D integer array of layer indices (length N).
    """
    return np.floor(frac_coords[:, axis] * n_bins).astype(int)


# ---------------------------------------------------------------------------
# Tilt implementations
# ---------------------------------------------------------------------------

def _in_phase(frac: np.ndarray, amplitude: float, perp_axis: int) -> np.ndarray:
    """In-phase (+) displacement along *perp_axis*.

    Displacement = amplitude * sin(2*pi * frac[:,perp_axis])

    Args:
        frac: Nx3 fractional coordinate array.
        amplitude: Tilt amplitude in Angstrom.
        perp_axis: Axis along which atoms are displaced.

    Returns:
        1-D displacement array of length N.
    """
    return amplitude * np.sin(2.0 * np.pi * frac[:, perp_axis])


def _out_of_phase(
    frac: np.ndarray,
    amplitude: float,
    perp_axis: int,
    layer_axis: int,
    n_bins: int,
) -> np.ndarray:
    """Out-of-phase (-) displacement along *perp_axis*.

    Displacement = amplitude * sin(2*pi * frac[:,perp_axis]) * (-1)^layer_index
    where layer_index is the discrete layer along *layer_axis*.

    Args:
        frac: Nx3 fractional coordinate array.
        amplitude: Tilt amplitude in Angstrom.
        perp_axis: Axis along which atoms are displaced.
        layer_axis: Axis used to determine the layer index.
        n_bins: Number of discrete layer bins.

    Returns:
        1-D displacement array of length N.
    """
    layer = compute_layer_indices(frac, layer_axis, n_bins)
    phase = (-1.0) ** layer
    return amplitude * np.sin(2.0 * np.pi * frac[:, perp_axis]) * phase


def apply_tilt(
    coords: np.ndarray,
    frac_coords: np.ndarray,
    tilt_type: str,
    amplitude: float,
    n_bins: int = 20,
) -> np.ndarray:
    """Apply a Glazer tilt pattern to Cartesian coordinates.

    Modifies atom positions to simulate octahedral tilting.  The displacements
    are applied in Cartesian space along the axes perpendicular to each tilt
    axis, using fractional coordinates to determine the sinusoidal phase.

    Convention
    ----------
    - In-phase (+):     ``amplitude * sin(2*pi * coord_perp)``
    - Out-of-phase (-): ``amplitude * sin(2*pi * coord_perp) * (-1)**layer``

    Axis mapping: axis 0 = a (x), axis 1 = b (y), axis 2 = c (z).

    Args:
        coords: Nx3 Cartesian coordinate array (modified in-place copy).
        frac_coords: Nx3 fractional coordinate array.
        tilt_type: Glazer tilt string, e.g. ``'a+a+a+'`` or ``'a0b-b-'``.
        amplitude: Tilt amplitude in Angstrom.
        n_bins: Number of discrete layers for out-of-phase determination.

    Returns:
        New Nx3 Cartesian coordinate array with displacements applied.

    Raises:
        ValueError: If *tilt_type* is not a recognised Glazer pattern.
    """
    c = coords.copy()
    f = frac_coords

    def ip(perp: int) -> np.ndarray:
        """In-phase displacement along *perp* axis."""
        return _in_phase(f, amplitude, perp)

    def op(perp: int, layer: int) -> np.ndarray:
        """Out-of-phase displacement along *perp*, layered along *layer*."""
        return _out_of_phase(f, amplitude, perp, layer, n_bins)

    # Each tilt acts on the PERPENDICULAR axes.
    # Tilt about z (c) -> displace x (0) and y (1)
    # Tilt about x (a) -> displace y (1) and z (2)
    # Tilt about y (b) -> displace x (0) and z (2)

    if tilt_type == "a+a+a+":
        # In-phase about all three axes, same amplitude
        c[:, 1] += ip(0)   # tilt about a -> displace b
        c[:, 2] += ip(0)   # tilt about a -> displace c
        c[:, 0] += ip(1)   # tilt about b -> displace a
        c[:, 2] += ip(1)   # tilt about b -> displace c
        c[:, 0] += ip(2)   # tilt about c -> displace a
        c[:, 1] += ip(2)   # tilt about c -> displace b

    elif tilt_type == "a+a+a-":
        # In-phase about a and b; out-of-phase about c
        c[:, 1] += ip(0); c[:, 2] += ip(0)
        c[:, 0] += ip(1); c[:, 2] += ip(1)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a+a-a+":
        # In-phase about a and c; out-of-phase about b
        c[:, 1] += ip(0); c[:, 2] += ip(0)
        c[:, 0] += op(1, 1); c[:, 2] += op(1, 1)
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a-a-a-":
        # Out-of-phase about all three axes
        c[:, 1] += op(0, 0); c[:, 2] += op(0, 0)
        c[:, 0] += op(1, 1); c[:, 2] += op(1, 1)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a0a0a+":
        # No tilt about a, b; in-phase about c
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a0a0a-":
        # No tilt about a, b; out-of-phase about c
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a0b+b+":
        # No tilt about a; in-phase about b and c (same amplitude)
        c[:, 0] += ip(1); c[:, 2] += ip(1)
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a0b+b-":
        # No tilt about a; in-phase about b; out-of-phase about c
        c[:, 0] += ip(1); c[:, 2] += ip(1)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a0b-b-":
        # No tilt about a; out-of-phase about b and c
        c[:, 0] += op(1, 1); c[:, 2] += op(1, 1)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a0a0b+":
        # No tilt about a and b; in-phase about c (b magnitude, alias)
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a0a0b-":
        # No tilt about a and b; out-of-phase about c (b magnitude, alias)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a+a0c+":
        # In-phase about a; no tilt about b; in-phase about c (different magnitudes
        # — here we use the same amplitude for both; pass distinct amplitudes via
        # separate calls if needed)
        c[:, 1] += ip(0); c[:, 2] += ip(0)
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a-a0c-":
        # Out-of-phase about a; no tilt about b; out-of-phase about c
        c[:, 1] += op(0, 0); c[:, 2] += op(0, 0)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    elif tilt_type == "a+b+c+":
        # In-phase about all three axes (different magnitudes — same amplitude here)
        c[:, 1] += ip(0); c[:, 2] += ip(0)
        c[:, 0] += ip(1); c[:, 2] += ip(1)
        c[:, 0] += ip(2); c[:, 1] += ip(2)

    elif tilt_type == "a-b-c-":
        # Out-of-phase about all three axes (different magnitudes — same amplitude here)
        c[:, 1] += op(0, 0); c[:, 2] += op(0, 0)
        c[:, 0] += op(1, 1); c[:, 2] += op(1, 1)
        c[:, 0] += op(2, 2); c[:, 1] += op(2, 2)

    else:
        raise ValueError(f"Unknown tilt type: '{tilt_type}'")

    return c


# ---------------------------------------------------------------------------
# Fractional coordinate helper
# ---------------------------------------------------------------------------

def cartesian_to_fractional(
    coords: np.ndarray,
    lattice: np.ndarray,
) -> np.ndarray:
    """Convert Cartesian coordinates to fractional.

    Args:
        coords: Nx3 Cartesian array.
        lattice: 3x3 lattice vector matrix (rows are vectors).

    Returns:
        Nx3 fractional coordinate array.
    """
    return coords @ np.linalg.inv(lattice)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

TILT_TYPES = [
    "a+a+a+", "a+a+a-", "a+a-a+", "a-a-a-",
    "a0a0a+", "a0a0a-", "a0b+b+", "a0b+b-",
    "a0b-b-", "a0a0b+", "a0a0b-", "a+a0c+",
    "a-a0c-", "a+b+c+", "a-b-c-",
]


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for octahedral_tilt.py."""
    p = argparse.ArgumentParser(
        description="Apply a Glazer octahedral tilt to a POSCAR file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--poscar",
        default=None,
        metavar="FILE",
        help="Input POSCAR file (prompted if omitted).",
    )
    p.add_argument(
        "--tilt",
        choices=TILT_TYPES,
        default=None,
        metavar="TYPE",
        help=(
            "Glazer tilt type. Choices: " + ", ".join(TILT_TYPES) +
            " (prompted if omitted)."
        ),
    )
    p.add_argument(
        "--magnitude",
        type=float,
        default=0.02,
        metavar="FLOAT",
        help="Tilt amplitude in Angstrom (default: 0.02).",
    )
    p.add_argument(
        "--output",
        default="POSCAR_tilted",
        metavar="FILE",
        help="Output POSCAR file (default: POSCAR_tilted).",
    )
    p.add_argument(
        "--layer-bins",
        type=int,
        default=20,
        metavar="N",
        help="Number of discrete layer bins for out-of-phase tilts (default: 20).",
    )
    return p


def main() -> None:
    """Entry point for octahedral_tilt.py."""
    args = build_parser().parse_args()

    # --- POSCAR ---
    poscar = args.poscar
    if poscar is None:
        poscar = input("Enter the POSCAR filename: ").strip()
        if not poscar:
            sys.exit("[FAIL] No POSCAR file specified.")

    try:
        scale, lattice, elements, num_atoms, coords = read_poscar(poscar)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"[FAIL] {exc}")

    # --- Tilt type ---
    tilt_type = args.tilt
    if tilt_type is None:
        print("Available octahedral tilts:")
        for i, t in enumerate(TILT_TYPES, 1):
            print(f"  {i:2d}: {t}")
        try:
            choice = int(input("Choose a tilt type by number: ")) - 1
            if not (0 <= choice < len(TILT_TYPES)):
                sys.exit("[FAIL] Invalid choice.")
            tilt_type = TILT_TYPES[choice]
        except ValueError:
            sys.exit("[FAIL] Invalid input — must be an integer.")

    # Convert Cartesian to fractional for displacement calculation
    frac_coords = cartesian_to_fractional(coords, lattice)

    try:
        tilted_coords = apply_tilt(
            coords, frac_coords, tilt_type, args.magnitude, args.layer_bins
        )
    except ValueError as exc:
        sys.exit(f"[FAIL] {exc}")

    write_poscar(args.output, scale, lattice, elements, num_atoms, tilted_coords)
    print(f"[OK] Tilt '{tilt_type}' applied (amplitude={args.magnitude} A).")
    print(f"[OK] Saved to: {args.output}")


if __name__ == "__main__":
    main()
