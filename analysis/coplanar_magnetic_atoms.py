#!/usr/bin/env python3
"""coplanar_magnetic_atoms.py — Assign Antiferromagnetic Signs by Atom Plane

Identifies coplanar groups for a user-supplied subset of atoms in a POSCAR /
CONTCAR and assigns +/- magnetic signs in blocks of L planes.

Reproducibility
---------------
Every run writes a ``run_parameters.txt`` file containing the exact command
that would reproduce the same output.  This makes it easy to re-run with the
same settings or document the workflow.

Outputs
-------
- ``MAGMOM``           – line suitable for VASP INCAR
- ``coplanar_atoms.txt`` – detailed table of plane assignment
- ``run_parameters.txt`` – command-line reproducibility record

Usage (full CLI)
-----------------
::

    python coplanar_magnetic_atoms.py POSCAR [X,Y,Z] [ATOMS] [TOL] [L] [M]

All arguments after POSCAR are optional; missing ones are prompted
interactively.  Atom selection can be element symbols (``"Fe Ni"``),
1-based indices (``"1 2 3"``), or ``"all"``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import re

# ANSI colour codes for terminal output (defined at module level so they are
# available whether main() is called directly or imported)
GREEN = "\033[32m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# POSCAR reader
# ---------------------------------------------------------------------------

def read_poscar(fname: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parse a POSCAR / CONTCAR file.

    Args:
        fname: Path to the POSCAR or CONTCAR file.

    Returns:
        ``(lattice, frac_coords, elements)`` where:

        - ``lattice``     – 3x3 array of lattice vectors in Angstrom.
        - ``frac_coords`` – Nx3 array of fractional coordinates.
        - ``elements``    – 1-D string array of element labels per atom.

    Raises:
        FileNotFoundError: If *fname* does not exist.
        ValueError: If the file cannot be parsed.
    """
    txt = Path(fname).read_text().splitlines()
    scale = float(txt[1])
    lattice = np.array([[float(x) for x in ln.split()] for ln in txt[2:5]]) * scale
    symbols = txt[5].split()
    counts = list(map(int, txt[6].split()))
    natoms = sum(counts)

    ptr = 7
    if txt[ptr][0].lower() == "s":   # Selective dynamics line
        ptr += 1
    cartesian = txt[ptr][0].lower() in ("c", "k")
    ptr += 1                          # now at first coordinate line

    coords = np.array(
        [[float(x) for x in txt[i].split()[:3]] for i in range(ptr, ptr + natoms)]
    )
    if cartesian:
        coords = coords @ np.linalg.inv(lattice)

    elements = np.repeat(symbols, counts)
    return lattice, coords, elements


# ---------------------------------------------------------------------------
# Interactive helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, default=None, cast=str):
    """Prompt the user and return the cast value or default.

    Args:
        prompt: Display string (without the default hint).
        default: Value returned when the user provides no input.
        cast: Callable used to convert the input string.

    Returns:
        ``cast(user_input)`` if the user typed something, else ``default``.
    """
    tail = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{tail}: ").strip()
    return cast(val) if val else default


def parse_vector(vector_str: str) -> np.ndarray:
    """Parse a vector string in ``[X,Y,Z]`` format.

    Args:
        vector_str: String like ``"[1,0,0]"`` or ``"[0.5,0.5,0]"``.

    Returns:
        3-element numpy float array.

    Raises:
        ValueError: If the format is wrong or components are non-numeric.
    """
    vector_str = vector_str.strip()
    if not (vector_str.startswith("[") and vector_str.endswith("]")):
        raise ValueError("Vector must be in format [X,Y,Z]")
    content = vector_str[1:-1]
    try:
        components = [float(x.strip()) for x in content.split(",")]
    except ValueError:
        raise ValueError("Vector components must be numbers")
    if len(components) != 3:
        raise ValueError("Vector must have exactly 3 components")
    return np.array(components)


def get_poscar_file() -> str:
    """Interactively prompt for a valid POSCAR file path.

    Returns:
        Path string to the POSCAR file.
    """
    while True:
        fname = input("Enter POSCAR file path: ").strip()
        if not fname:
            print("Please provide a file path.")
            continue
        if not Path(fname).exists():
            print(f"File '{fname}' not found. Please check the path.")
            continue
        try:
            read_poscar(fname)
            return fname
        except Exception as exc:
            print(f"Error reading POSCAR: {exc}")


def get_orthogonal_vector() -> np.ndarray:
    """Interactively prompt for the normal vector in ``[X,Y,Z]`` format.

    Returns:
        3-element numpy float array.
    """
    while True:
        s = input("Enter orthogonal vector [X,Y,Z] (e.g. [1,0,0]): ").strip()
        if not s:
            print("Please provide a vector.")
            continue
        try:
            return parse_vector(s)
        except ValueError as exc:
            print(f"Error: {exc}")


def parse_atom_selection(atom_str: str, elems: np.ndarray) -> np.ndarray:
    """Parse an atom selection string and return a boolean mask.

    Accepts ``"all"``, space-separated 1-based indices, or space-separated
    element symbols.

    Args:
        atom_str: Selection string from the user or CLI.
        elems: Array of element labels per atom.

    Returns:
        Boolean numpy array of length len(elems).
    """
    natoms = len(elems)
    if atom_str.lower() == "all":
        return np.ones(natoms, bool)

    parts = atom_str.split()
    if all(p.isdigit() for p in parts):
        idx = [int(x) - 1 for x in parts]
        mask = np.zeros(natoms, bool)
        mask[idx] = True
        return mask

    keep = set(parts)
    return np.array([e in keep for e in elems])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for coplanar_magnetic_atoms.py."""
    cli_args = sys.argv[1:]

    poscar: str | None = None
    n_vec: np.ndarray | None = None
    atoms: str | None = None
    tol: float | None = None
    L: int | None = None
    M: float | None = None

    # Parse positional CLI arguments
    if len(cli_args) >= 1:
        poscar = cli_args[0]
        if not Path(poscar).exists():
            sys.exit(f"[FAIL] POSCAR file '{poscar}' not found.")

    if len(cli_args) >= 2:
        try:
            n_vec = parse_vector(cli_args[1])
        except ValueError as exc:
            sys.exit(f"[FAIL] Invalid vector '{cli_args[1]}': {exc}")

    if len(cli_args) >= 3:
        atoms = cli_args[2]

    if len(cli_args) >= 4:
        try:
            tol = float(cli_args[3])
        except ValueError:
            sys.exit(f"[FAIL] Tolerance must be a number, got '{cli_args[3]}'")

    if len(cli_args) >= 5:
        try:
            L = int(cli_args[4])
        except ValueError:
            sys.exit(f"[FAIL] Layers must be an integer, got '{cli_args[4]}'")

    if len(cli_args) >= 6:
        try:
            M = float(cli_args[5])
        except ValueError:
            sys.exit(f"[FAIL] Magnitude must be a number, got '{cli_args[5]}'")

    if len(cli_args) > 6:
        print("Too many arguments provided.")
        print(__doc__)
        sys.exit(1)

    # Fill in any missing arguments interactively
    if poscar is None:
        print("Interactive mode — please provide the following inputs:")
        poscar = get_poscar_file()

    if n_vec is None:
        n_vec = get_orthogonal_vector()

    if np.allclose(n_vec, 0):
        sys.exit("[FAIL] Normal vector must be non-zero.")

    # Read POSCAR
    try:
        lattice, frac, elems = read_poscar(poscar)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"[FAIL] {exc}")

    natoms = len(elems)

    # --- Atom selection ---
    print("\nElements present:", " ".join(sorted(set(elems))))
    if atoms is None:
        sel = input("Atoms of interest (symbols OR indices; blank = all): ").split()
        if not sel:
            mask = np.ones(natoms, bool)
        elif sel[0].isdigit():
            idx = [int(x) - 1 for x in sel]
            mask = np.zeros(natoms, bool)
            mask[idx] = True
        else:
            keep = set(sel)
            mask = np.array([e in keep for e in elems])
    else:
        try:
            mask = parse_atom_selection(atoms, elems)
        except Exception as exc:
            sys.exit(f"[FAIL] Atom selection error: {exc}")

    if not mask.any():
        sys.exit("[FAIL] Atom selection matched no atoms.")

    # --- Numeric parameters ---
    if tol is None:
        tol = float(ask("Coplanarity tolerance (Å)", 0.02, float))
    if L is None:
        L = int(ask("Layers per ferromagnetic block L", 1, int))
    if M is None:
        # Note: the non-breaking hyphen in "Magnetic-moment" uses a standard hyphen here
        M = float(ask("Magnetic-moment magnitude M", 1, float))

    if tol <= 0:
        sys.exit("[FAIL] Tolerance must be positive.")
    if L <= 0:
        sys.exit("[FAIL] Layers L must be a positive integer.")

    # --- Projections ---
    n_cart = n_vec @ lattice if np.all(np.abs(n_vec) <= 1) else n_vec
    n_hat = n_cart / np.linalg.norm(n_cart)
    cart = frac @ lattice
    proj = cart @ n_hat

    planes: dict[int, list] = {}
    for i, p in enumerate(proj):
        if not mask[i]:
            continue
        pid = next(
            (k for k, (ref, _) in planes.items() if abs(p - ref) < tol),
            None,
        )
        if pid is None:
            pid = len(planes)
            planes[pid] = [p, []]
        planes[pid][1].append(i)

    ordered = sorted(planes.items(), key=lambda kv: kv[1][0])

    # --- Assign signs and build MAGMOM ---
    magmom_values = np.zeros(natoms)
    table_lines: list[str] = []
    for plane_id, (_, idx_list) in enumerate(a[1] for a in ordered):
        sign = +1 if (plane_id // L) % 2 == 0 else -1
        for idx in idx_list:
            magmom_values[idx] = sign * M
            fc = " ".join(f"{x:.3f}" for x in frac[idx])
            table_lines.append(
                f"{idx+1:<10d} {elems[idx]:<7} {plane_id:<8d} {sign:+d}   {fc}"
            )

    # --- Write MAGMOM ---
    with open("MAGMOM", "w") as f:
        f.write("MAGMOM = " + "  ".join(f"{v:+g}" for v in magmom_values) + "\n")
    print(f"\n{GREEN}Created MAGMOM file with {natoms} entries.{RESET}")

    # --- Write detailed table ---
    with open("coplanar_atoms.txt", "w") as f:
        f.write("atom_index element plane_ID sign frac_coords\n")
        f.write("---------------------------------------------\n")
        f.write("\n".join(table_lines) + "\n")
    print(f"{GREEN}Wrote detailed plane assignment to coplanar_atoms.txt{RESET}")

    # --- Save run parameters for reproducibility ---
    # Reconstruct how the atom selection would be expressed on the CLI
    if np.all(mask):
        atoms_str = "all"
    else:
        selected_elements: set[str] = {elems[i] for i in range(natoms) if mask[i]}
        element_mask = np.array([e in selected_elements for e in elems])
        if np.array_equal(mask, element_mask):
            atoms_str = " ".join(sorted(selected_elements))
        else:
            atoms_str = " ".join(str(i + 1) for i in range(natoms) if mask[i])

    vector_str = f"[{n_vec[0]},{n_vec[1]},{n_vec[2]}]"
    cmd_line = (
        f"./coplanar_magnetic_atoms.py {poscar} {vector_str} "
        f'"{atoms_str}" {tol} {L} {M}'
    )

    with open("run_parameters.txt", "w") as f:
        f.write("# Coplanar Magnetic Atoms - Run Parameters\n")
        f.write("# Reproduce this run with:\n#\n")
        f.write(f"{cmd_line}\n#\n")
        f.write(f"# POSCAR file          : {poscar}\n")
        f.write(f"# Orthogonal vector    : {vector_str}\n")
        f.write(f"# Atoms                : {atoms_str}\n")
        f.write(f"# Tolerance            : {tol} Angstrom\n")
        f.write(f"# Layers per block     : {L}\n")
        f.write(f"# Magnetic moment mag. : {M}\n")
        f.write(f"# Total atoms selected : {np.sum(mask)}/{natoms}\n")
        f.write(f"# Planes found         : {len(ordered)}\n")
    print(f"{GREEN}Saved run parameters to run_parameters.txt{RESET}")

    # --- Echo to stdout ---
    print("\natom_index element plane_ID sign frac_coords")
    print("---------------------------------------------")
    print("\n".join(table_lines))
    print(
        f"\n{len(ordered)} planes found (tol={tol} Ang). "
        f"Sign repeats every {L} plane(s).  M = {M}"
    )
    print(f"\nTo reproduce this run:\n{cmd_line}")


if __name__ == "__main__":
    main()
