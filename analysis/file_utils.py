"""File Utilities Module for Energy vs. C/A Analysis

Provides file-discovery and atom-count-reading utilities shared across the
energy analysis suite (energy_vs_ca.py, energy_vs_structure.py,
energy_plotting/plot_energy_vs_structure.py).

Expected format for atom_counts.dat
-------------------------------------
Whitespace-separated columns with an optional leading ``#`` on the header::

    # Directory  Species1  Species2  ...  Total
    dirname      N1        N2        ...  Ntotal

- The first column is a directory name (string key).
- Middle columns are per-species atom counts (integers).
- The last column must be labelled ``Total`` and equal the sum of per-species counts.
- Comment lines (``#``) and blank lines are skipped in the data section.
"""

from __future__ import annotations

import re
from pathlib import Path


def read_atom_counts(
    atom_file: Path,
) -> tuple[list[str], dict[str, dict]]:
    """Read atom_counts.dat and return species list and per-directory counts.

    Args:
        atom_file: Path to the atom_counts.dat file.

    Returns:
        A 2-tuple ``(species, data)`` where:

        - ``species`` – list of atomic-species names (strings), in header order,
          excluding the leading ``Directory`` and trailing ``Total`` columns.
        - ``data`` – dict mapping directory-name strings to
          ``{"species_counts": [int, ...], "total_atoms": int}``.

    Raises:
        FileNotFoundError: If atom_file does not exist.
        ValueError: If the header is missing or malformed.
    """
    if not atom_file.exists():
        raise FileNotFoundError(f"Atom counts file not found: {atom_file}")

    data: dict[str, dict] = {}

    with atom_file.open() as f:
        # Read the first non-blank line as the header (strip leading '#')
        header = ""
        for line in f:
            line = line.strip()
            if not line:
                continue
            header = line[1:].strip() if line.startswith("#") else line
            break

        if not header:
            raise ValueError("No valid header found in atom_counts.dat")

        header_parts = header.split()
        if len(header_parts) < 3 or header_parts[-1] != "Total":
            raise ValueError(
                "Header must contain 'Directory', species names, and 'Total'. "
                f"Found header: '{header}' "
                f"Parsed as: {header_parts}"
            )

        # Species are the columns between 'Directory' and 'Total'
        species: list[str] = header_parts[1:-1]

        # Process data lines
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) != len(header_parts):
                print(
                    f"Warning: Skipping malformed line "
                    f"(expected {len(header_parts)} columns, got {len(parts)}): {line}"
                )
                continue

            try:
                directory = parts[0]
                counts = list(map(int, parts[1:-1]))
                total = int(parts[-1])

                # Sanity-check that counts sum to the stated total
                if sum(counts) != total:
                    print(
                        f"Warning: Counts don't sum to total in "
                        f"{directory} ({sum(counts)} vs {total})"
                    )

                data[directory] = {"species_counts": counts, "total_atoms": total}
            except (ValueError, IndexError) as exc:
                print(f"Warning: Skipping malformed line: {line} ({exc})")
                continue

    return species, data


def find_paired_files(root: Path) -> list[tuple[Path, Path]]:
    """Find directories containing both atom_counts.dat and energies.dat.

    Searches recursively under ``root`` for ``atom_counts.dat`` files and
    checks whether a sibling ``energies.dat`` exists in the same directory.

    Args:
        root: Root directory to search.

    Returns:
        List of ``(atom_counts_path, energies_path)`` tuples.
    """
    pairs: list[tuple[Path, Path]] = []

    for atom_file in root.rglob("atom_counts.dat"):
        energy_file = atom_file.parent / "energies.dat"
        if energy_file.exists():
            pairs.append((atom_file, energy_file))
        else:
            print(f"No energies.dat found in {atom_file.parent}")

    return pairs


def get_display_name(atom_file: Path) -> str:
    """Create a short descriptive label from an atom_counts.dat path.

    Returns the last two meaningful path components joined by ``/``,
    e.g. ``"AFA/PBEsol+U_ICHARG_left"``.

    Args:
        atom_file: Path to the atom_counts.dat file.

    Returns:
        A human-readable dataset label string.
    """
    relevant_parts = [
        p for p in atom_file.parts
        if p not in (".", "..", "atom_counts.dat")
    ]

    if len(relevant_parts) >= 2:
        return "/".join(relevant_parts[-2:])
    elif len(relevant_parts) == 1:
        return relevant_parts[0]
    else:
        return atom_file.parent.name
