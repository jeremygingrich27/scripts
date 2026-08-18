#!/usr/bin/env python3
"""antiferromagnetic_planes.py — Assign Antiferromagnetic Signs by Plane

Identifies coplanar planes for a user-supplied subset of atoms in a POSCAR /
CONTCAR file and assigns +/- magnetic signs in blocks of L planes.

The sign assignment formula is::

    sign = +1 if (plane_id // L) % 2 == 0 else -1

where ``plane_id`` is the zero-based index of the plane (sorted by
projection along the normal vector) and ``L`` is the number of planes per
ferromagnetic block.

Outputs
-------
- ``MAGMOM``           – line suitable for VASP INCAR
- ``coplanar_planes.txt`` – detailed table of plane assignment

Usage
-----
::

    python antiferromagnetic_planes.py POSCAR [NX,NY,NZ]

If fewer than 2 arguments are provided the script falls back to interactive
prompts for the missing values.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

# ANSI colour codes for terminal output
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

        - ``lattice``    – 3x3 array of lattice vectors in Angstrom.
        - ``frac_coords``– Nx3 array of fractional coordinates.
        - ``elements``   – 1-D string array of element labels per atom.

    Raises:
        FileNotFoundError: If *fname* does not exist.
        ValueError: If the file cannot be parsed as a valid POSCAR.
    """
    from pathlib import Path

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
# Interactive helper
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


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Assign antiferromagnetic signs to coplanar planes in a POSCAR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("poscar", nargs="?", default=None, help="Path to POSCAR/CONTCAR file.")
    p.add_argument(
        "normal",
        nargs="?",
        default=None,
        help="Normal vector as comma-separated components, e.g. '0,0,1'.",
    )
    p.add_argument(
        "--atoms",
        default=None,
        metavar="SELECTION",
        help="Atom selection: element symbols (e.g. 'Fe Ni') or indices (e.g. '1 2 3').",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=None,
        metavar="TOL",
        help="Coplanarity tolerance in Angstrom (default: 0.02).",
    )
    p.add_argument(
        "--layers",
        type=int,
        default=None,
        metavar="L",
        help="Planes per ferromagnetic block L (default: 1).",
    )
    p.add_argument(
        "--magnitude",
        type=float,
        default=None,
        metavar="M",
        help="Magnetic moment magnitude M (default: 1).",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for antiferromagnetic_planes.py."""
    args = build_parser().parse_args()

    # --- POSCAR ---
    poscar = args.poscar
    if poscar is None:
        poscar = input("POSCAR file: ").strip()
        if not poscar:
            sys.exit("[FAIL] No POSCAR file specified.")

    try:
        lattice, frac, elems = read_poscar(poscar)
    except (FileNotFoundError, ValueError, IndexError) as exc:
        sys.exit(f"[FAIL] Cannot read POSCAR '{poscar}': {exc}")

    natoms = len(elems)

    # --- Normal vector ---
    if args.normal is not None:
        try:
            n_vec = np.array([float(x) for x in args.normal.split(",")])
            if len(n_vec) != 3:
                raise ValueError("Need exactly 3 components.")
        except ValueError as exc:
            sys.exit(f"[FAIL] Invalid normal vector: {exc}")
    else:
        raw = input("Normal vector (comma-separated x,y,z e.g. 0,0,1): ").strip()
        try:
            n_vec = np.array([float(x) for x in raw.split(",")])
            if len(n_vec) != 3:
                raise ValueError
        except ValueError:
            sys.exit("[FAIL] Invalid normal vector — need three comma-separated numbers.")

    if np.allclose(n_vec, 0):
        sys.exit("[FAIL] Normal vector must be non-zero.")

    # --- Atom selection ---
    print("\nElements present:", " ".join(sorted(set(elems))))
    if args.atoms is not None:
        sel = args.atoms.split()
    else:
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

    if not mask.any():
        sys.exit("[FAIL] Atom selection matched no atoms.")

    # --- Numeric parameters ---
    tol = args.tolerance if args.tolerance is not None else ask("Coplanarity tolerance (Å)", 0.02, float)
    L = args.layers if args.layers is not None else ask("Layers per ferromagnetic block L", 1, int)
    M = args.magnitude if args.magnitude is not None else ask("Magnetic moment magnitude M", 1, float)

    if tol <= 0:
        sys.exit("[FAIL] Tolerance must be positive.")
    if L <= 0:
        sys.exit("[FAIL] Layers L must be a positive integer.")

    # --- Compute projections along the normal ---
    # If components are all <= 1 treat as fractional; otherwise Cartesian
    n_cart = n_vec @ lattice if np.all(np.abs(n_vec) <= 1) else n_vec
    n_hat = n_cart / np.linalg.norm(n_cart)
    cart = frac @ lattice
    proj = cart @ n_hat

    # Group atoms into coplanar planes (within tolerance)
    planes: dict[int, list] = {}   # plane_id -> [ref_proj, [atom_idx]]
    for i, p in enumerate(proj):
        if not mask[i]:
            continue
        # Find an existing plane close enough
        pid = next(
            (k for k, (ref, _) in planes.items() if abs(p - ref) < tol),
            None,
        )
        if pid is None:
            pid = len(planes)
            planes[pid] = [p, []]
        planes[pid][1].append(i)

    ordered = sorted(planes.items(), key=lambda kv: kv[1][0])

    # --- Assign +/- signs and build MAGMOM array ---
    magmom_values = np.zeros(natoms)
    table_lines: list[str] = []
    for plane_id, (_, idx_list) in enumerate(a[1] for a in ordered):
        # Sign repeats every L planes: even blocks (+), odd blocks (-)
        sign = +1 if (plane_id // L) % 2 == 0 else -1
        for idx in idx_list:
            magmom_values[idx] = sign * M
            fc = " ".join(f"{x:.3f}" for x in frac[idx])
            table_lines.append(
                f"{idx+1:<10d} {elems[idx]:<7} {plane_id:<8d} {sign:+d}   {fc}"
            )

    # --- Write MAGMOM file ---
    with open("MAGMOM", "w") as f:
        line = "MAGMOM = " + "  ".join(f"{v:+g}" for v in magmom_values)
        f.write(line + "\n")
    print(f"\n{GREEN}Created MAGMOM file with {natoms} entries.{RESET}")

    # --- Write detailed table ---
    with open("coplanar_planes.txt", "w") as f:
        f.write("atom_index element plane_ID sign frac_coords\n")
        f.write("---------------------------------------------\n")
        f.write("\n".join(table_lines) + "\n")
    print(f"{GREEN}Wrote detailed plane assignment to coplanar_planes.txt{RESET}")

    # --- Echo table to stdout ---
    print("\natom_index element plane_ID sign frac_coords")
    print("---------------------------------------------")
    print("\n".join(table_lines))
    print(
        f"\n{len(ordered)} planes found (tol={tol} A). "
        f"Sign repeats every {L} plane(s).  M = {M}"
    )


if __name__ == "__main__":
    main()
