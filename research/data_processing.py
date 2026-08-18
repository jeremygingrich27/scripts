"""Data Processing Module for Energy vs. C/A Analysis

Provides parsing and manipulation functions for energy-vs-c/a-ratio data
used across the energy analysis suite (energy_vs_ca.py, energy_vs_structure.py,
dyn_matrix.py).

Expected format for energies.dat
---------------------------------
Whitespace-separated columns::

    Directory  a  b  c  total_energy

- The first column is a directory name (string, ignored in arithmetic).
- Columns 2–4 are the a, b, c lattice parameters in Angstroms.
- Column 5 is the DFT total energy in eV.
- Header lines starting with "directory" (case-insensitive) are skipped.
- Blank lines are skipped.
"""

from __future__ import annotations

import numpy as np
from pathlib import Path


def parse_energy_data(
    fpath: Path,
    atoms_per_fu: int,
    total_atoms: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Parse energies.dat and return sorted arrays for energy analysis.

    Reads whitespace-delimited rows of the form::

        <directory>  <a>  <b>  <c>  <total_energy>

    The c/a ratio is computed as ``c / ((a + b) / 2)`` to handle
    slightly non-square in-plane lattice vectors.

    Args:
        fpath: Path to the energies.dat file.
        atoms_per_fu: Number of atoms per formula unit (must be > 0).
        total_atoms: Total number of atoms in the supercell (must be > 0).

    Returns:
        A 5-tuple of 1-D numpy arrays, all sorted by ascending c/a ratio:

        - ``c_over_a``        – dimensionless c/a ratio
        - ``energies_per_fu`` – total energy divided by number of formula units (eV/f.u.)
        - ``a_values``        – a lattice parameter (Angstrom)
        - ``b_values``        – b lattice parameter (Angstrom)
        - ``c_values``        – c lattice parameter (Angstrom)

    Raises:
        ValueError: If atoms_per_fu or total_atoms is not positive.
        FileNotFoundError: If fpath does not exist.
    """
    if atoms_per_fu <= 0:
        raise ValueError(f"atoms_per_fu must be > 0, got {atoms_per_fu}")
    if total_atoms <= 0:
        raise ValueError(f"total_atoms must be > 0, got {total_atoms}")
    if not fpath.exists():
        raise FileNotFoundError(f"Energy file not found: {fpath}")

    formula_units = total_atoms / atoms_per_fu

    # Accumulate into lists so we can index with [idx] after argsort
    c_over_a_list: list[float] = []
    energies_list: list[float] = []
    a_list: list[float] = []
    b_list: list[float] = []
    c_list: list[float] = []

    with fpath.open() as f:
        for line in f:
            if not line.strip() or line.lower().startswith("directory"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                a, b, c, energy = map(float, parts[1:5])
                ca = c / ((a + b) / 2)
                c_over_a_list.append(ca)
                energies_list.append(energy / formula_units)
                a_list.append(a)
                b_list.append(b)
                c_list.append(c)
            except ValueError:
                continue

    c_over_a = np.array(c_over_a_list)
    energies = np.array(energies_list)
    a_arr = np.array(a_list)
    b_arr = np.array(b_list)
    c_arr = np.array(c_list)

    idx = np.argsort(c_over_a)
    return c_over_a[idx], energies[idx], a_arr[idx], b_arr[idx], c_arr[idx]


def splice_datasets(
    seg1: tuple[np.ndarray, np.ndarray],
    seg2: tuple[np.ndarray, np.ndarray],
    cutoff: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Combine two (x, y) datasets by splicing at a c/a cutoff value.

    Points from ``seg1`` with ``x <= cutoff`` are retained; points from
    ``seg2`` with ``x > cutoff`` are retained. The result is sorted by
    ascending x.

    Args:
        seg1: First dataset as (x_array, y_array).
        seg2: Second dataset as (x_array, y_array).
        cutoff: c/a value at which the splice occurs.

    Returns:
        Combined (x, y) tuple sorted by ascending x.
    """
    mask1 = seg1[0] <= cutoff
    mask2 = seg2[0] > cutoff
    x_combined = np.concatenate([seg1[0][mask1], seg2[0][mask2]])
    y_combined = np.concatenate([seg1[1][mask1], seg2[1][mask2]])
    idx = np.argsort(x_combined)
    return x_combined[idx], y_combined[idx]
