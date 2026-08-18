#!/usr/bin/env python3
"""smodes_extractor.py — Extract Symmetry-Mode Displacements from SMODES Output

Parses an SMODES displacement file, extracts the atomic displacement vectors
for each symmetry mode, reorders atoms by element and number within each
block, and writes three output files:

1. **Original file** (overwritten, with atoms reordered) — backed up as
   ``<filename>.bak`` before modification.
2. **<stem>_normfactors.txt** — all lines containing ``normfactor``.
3. **<stem>_matrix.csv** — displacement matrix (rows = atoms x components,
   columns = modes).

Expected input format
----------------------
::

    Displacive mode definitions
    atom    x        y        z        dx      dy      dz
    Cu1 normfactor 0.123 ...
    Cu1     0.0  0.5  0.0  0.01  0.0  0.0
    Cu2     0.5  0.0  0.0  0.0  0.01  0.0
    ...

Each block starts with a header line containing ``normfactor``, followed by
atom coordinate lines with at least 7 columns (atom dx dy dz are in
columns 5-7, 1-indexed).

Usage
-----
::

    python smodes_extractor.py <filename>
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_file(filename: str) -> Path | None:
    """Search for *filename* in the current working directory.

    Args:
        filename: Bare filename to locate.

    Returns:
        Path object if found, ``None`` otherwise.
    """
    path = Path.cwd() / filename
    if path.exists():
        return path
    print(f"[FAIL] File '{filename}' not found in {Path.cwd()}")
    return None


def backup_file(file_path: Path) -> Path | None:
    """Back up *file_path* to ``<file_path>.bak``.

    Args:
        file_path: Path to the file to back up.

    Returns:
        Path to the backup file, or ``None`` on failure.
    """
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    try:
        shutil.copy2(file_path, backup_path)
        print(f"[OK] Backup created: {backup_path}")
        return backup_path
    except OSError as exc:
        print(f"[FAIL] Cannot create backup: {exc}")
        return None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def extract_normfactor_lines(file_path: Path) -> list[str]:
    """Return all lines in *file_path* that contain the word ``normfactor``.

    Args:
        file_path: Path to the SMODES displacement file.

    Returns:
        List of stripped line strings.
    """
    lines: list[str] = []
    try:
        with file_path.open() as f:
            for line in f:
                if "normfactor" in line:
                    lines.append(line.strip())
    except OSError as exc:
        print(f"[WARN] Cannot read normfactor lines: {exc}")
    return lines


def parse_file_structure(file_path: Path) -> list[dict]:
    """Parse the SMODES file into mode blocks.

    Each block has a ``header`` (the normfactor line) and a ``data`` list
    of raw atom-displacement lines (those with >= 7 columns).

    Args:
        file_path: Path to the SMODES displacement file.

    Returns:
        List of dicts with keys ``'header'`` and ``'data'``.
    """
    blocks: list[dict] = []
    current_block: dict | None = None

    try:
        with file_path.open() as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                if "normfactor" in stripped:
                    if current_block is not None:
                        blocks.append(current_block)
                    current_block = {"header": stripped, "data": []}
                elif current_block is not None and not stripped.startswith(("Displacive", "atom")):
                    # Only keep lines with enough columns to have displacements
                    if len(stripped.split()) >= 7:
                        current_block["data"].append(stripped)
    except OSError as exc:
        print(f"[FAIL] Cannot parse file structure: {exc}")
        return []

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def get_atomic_species(blocks: list[dict]) -> list[str]:
    """Extract unique atomic species names from all blocks.

    The element symbol is obtained by stripping trailing digits only,
    so multi-character symbols like ``Ca`` or ``Mo`` are preserved correctly.

    Args:
        blocks: List of mode blocks from :func:`parse_file_structure`.

    Returns:
        Sorted list of unique element symbol strings.
    """
    species: set[str] = set()
    for block in blocks:
        for line in block["data"]:
            atom_name = line.split()[0]
            # Strip trailing digits only (not all digits) to preserve Ca, Mo, etc.
            element = re.sub(r"\d+$", "", atom_name)
            species.add(element)
    return sorted(species)


def extract_atom_number(atom_name: str) -> int:
    """Extract the trailing integer from an atom name like ``Cu29``.

    Args:
        atom_name: Atom identifier string.

    Returns:
        Trailing integer, or 0 if none found.
    """
    match = re.search(r"(\d+)$", atom_name)
    return int(match.group(1)) if match else 0


# ---------------------------------------------------------------------------
# Reordering & matrix creation
# ---------------------------------------------------------------------------

def reorder_atoms_in_blocks(blocks: list[dict]) -> list[dict]:
    """Sort atoms within each block by element name then atom number.

    Args:
        blocks: List of mode blocks.

    Returns:
        New list of blocks with ``data`` lines sorted.
    """
    reordered: list[dict] = []
    for block in blocks:
        sorted_data = sorted(
            block["data"],
            key=lambda line: (
                re.sub(r"\d+$", "", line.split()[0]),   # element symbol
                extract_atom_number(line.split()[0]),    # atom number
            ),
        )
        reordered.append({"header": block["header"], "data": sorted_data})
    return reordered


def extract_mode_name(header_line: str) -> str:
    """Extract the mode name from a header line (text before 'normfactor').

    Args:
        header_line: The normfactor header line.

    Returns:
        Mode name string.
    """
    if "normfactor" in header_line:
        return header_line.split("normfactor")[0].strip()
    return header_line.strip()


def create_displacement_matrix(
    blocks: list[dict],
) -> tuple[list[list[float]], list[str], list[str]]:
    """Build a displacement matrix from mode blocks.

    Rows are indexed by (atom, component) pairs; columns by mode.

    Args:
        blocks: Reordered list of mode blocks.

    Returns:
        ``(matrix, row_labels, mode_names)`` where ``matrix[row][col]``
        is the displacement component value.
    """
    # Collect all atom names across all blocks
    all_atoms: set[str] = set()
    for block in blocks:
        for line in block["data"]:
            all_atoms.add(line.split()[0])

    # Sort atoms: by element then by trailing number
    def _sort_key(name: str) -> tuple[str, int]:
        return re.sub(r"\d+$", "", name), extract_atom_number(name)

    sorted_atoms = sorted(all_atoms, key=_sort_key)

    # Row labels: atom_dx, atom_dy, atom_dz
    row_labels: list[str] = []
    for atom in sorted_atoms:
        row_labels.extend([f"{atom}dx", f"{atom}dy", f"{atom}dz"])

    mode_names = [extract_mode_name(b["header"]) for b in blocks]

    n_rows = len(row_labels)
    n_cols = len(blocks)
    matrix: list[list[float]] = [[0.0] * n_cols for _ in range(n_rows)]

    for col_idx, block in enumerate(blocks):
        # Map atom name -> (dx, dy, dz)
        atom_disp: dict[str, tuple[float, float, float]] = {}
        for line in block["data"]:
            parts = line.split()
            atom_name = parts[0]
            try:
                dx, dy, dz = float(parts[4]), float(parts[5]), float(parts[6])
                atom_disp[atom_name] = (dx, dy, dz)
            except (ValueError, IndexError) as exc:
                print(f"[WARN] Cannot parse displacements for '{atom_name}': {exc}")
                continue

        for row_idx, row_label in enumerate(row_labels):
            if row_label.endswith("dx"):
                atom = row_label[:-2]
                if atom in atom_disp:
                    matrix[row_idx][col_idx] = atom_disp[atom][0]
            elif row_label.endswith("dy"):
                atom = row_label[:-2]
                if atom in atom_disp:
                    matrix[row_idx][col_idx] = atom_disp[atom][1]
            elif row_label.endswith("dz"):
                atom = row_label[:-2]
                if atom in atom_disp:
                    matrix[row_idx][col_idx] = atom_disp[atom][2]

    return matrix, row_labels, mode_names


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_normfactor_file(normfactor_lines: list[str], stem: str) -> str:
    """Write normfactor lines to a text file.

    Args:
        normfactor_lines: Lines containing 'normfactor'.
        stem: File stem (without extension) for naming the output.

    Returns:
        Output filename string.
    """
    out = f"{stem}_normfactors.txt"
    with open(out, "w") as f:
        f.write("Lines containing 'normfactor':\n")
        f.write("=" * 50 + "\n\n")
        for line in normfactor_lines:
            f.write(line + "\n")
    print(f"[OK] Normfactor lines written to: {out}")
    return out


def write_reordered_file(
    blocks: list[dict],
    file_path: Path,
) -> Path | None:
    """Overwrite *file_path* with reordered atom blocks (after backing up).

    Args:
        blocks: Reordered block list.
        file_path: Path to the original SMODES file.

    Returns:
        The overwritten path, or ``None`` on failure.
    """
    backup_path = backup_file(file_path)
    if backup_path is None:
        print("[FAIL] Backup failed. Aborting file replacement.")
        return None

    try:
        with file_path.open("w") as f:
            f.write("Displacive mode definitions\n")
            f.write("atom    x        y        z        dx      dy      dz   \n")
            for i, block in enumerate(blocks):
                if i > 0:
                    f.write("\n")
                f.write(block["header"] + "\n")
                for line in block["data"]:
                    f.write(line + "\n")
    except OSError as exc:
        print(f"[FAIL] Cannot write reordered file: {exc}")
        # Attempt to restore backup
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, file_path)
                print("[OK] Restored original file from backup.")
            except OSError:
                print("[FAIL] Could not restore backup — manual intervention needed.")
        return None

    print(f"[OK] Original file replaced with reordered data.")
    return file_path


def write_displacement_matrix(
    matrix: list[list[float]],
    row_labels: list[str],
    mode_names: list[str],
    stem: str,
) -> str:
    """Write the displacement matrix to a CSV file.

    Args:
        matrix: 2-D list of float displacement values.
        row_labels: Row label strings.
        mode_names: Column (mode) name strings.
        stem: File stem for naming the output CSV.

    Returns:
        Output filename string.
    """
    out = f"{stem}_matrix.csv"
    with open(out, "w") as f:
        # Header row: "Displacement", then mode names
        f.write("Displacement")
        for mode in mode_names:
            clean = mode.replace(",", ";").replace("\n", " ").strip()
            f.write(f',"{clean}"')
        f.write("\n")
        # Data rows
        for row_idx, label in enumerate(row_labels):
            f.write(label)
            for val in matrix[row_idx]:
                f.write(f",{val:.6f}")
            f.write("\n")
    print(f"[OK] Displacement matrix written to: {out}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for smodes_extractor.py."""
    if len(sys.argv) != 2:
        print("Usage: python smodes_extractor.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Searching for file: {filename}")

    file_path = find_file(filename)
    if file_path is None:
        sys.exit(1)

    print(f"Found: {file_path}")
    stem = Path(filename).stem

    # Extract normfactor lines
    print("\nExtracting normfactor lines...")
    normfactor_lines = extract_normfactor_lines(file_path)
    if not normfactor_lines:
        print("[FAIL] No lines containing 'normfactor' found.")
        sys.exit(1)
    print(f"  Found {len(normfactor_lines)} normfactor line(s).")
    write_normfactor_file(normfactor_lines, stem)

    # Parse structure into blocks
    print("\nParsing file structure...")
    blocks = parse_file_structure(file_path)
    if not blocks:
        print("[FAIL] No data blocks found.")
        sys.exit(1)
    print(f"  Found {len(blocks)} data block(s).")

    # Atomic species
    species = get_atomic_species(blocks)
    print(f"  Atomic species: {', '.join(species)}")

    # Reorder atoms
    print("\nReordering atoms within each block...")
    reordered_blocks = reorder_atoms_in_blocks(blocks)

    # Write reordered file (overwrites original after backup)
    write_reordered_file(reordered_blocks, file_path)

    # Create and write displacement matrix
    print("\nCreating displacement matrix...")
    matrix, row_labels, mode_names = create_displacement_matrix(reordered_blocks)
    print(f"  Matrix: {len(row_labels)} rows x {len(mode_names)} columns")
    write_displacement_matrix(matrix, row_labels, mode_names, stem)

    print("\n[OK] Processing complete.")


if __name__ == "__main__":
    main()
