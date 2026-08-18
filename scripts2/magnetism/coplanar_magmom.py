#!/usr/bin/env python3
"""
coplanar_magmom.py
Group a chosen subset of atoms in a POSCAR/CONTCAR into planes perpendicular to
a given vector, then assign alternating magnetic moments in blocks of L planes
and write a VASP-ready MAGMOM line.

Two block-value modes (mutually exclusive):
  * moment mode (default):  -M/--moment VALUE  -> blocks get +VALUE / -VALUE
  * P/N mode:               --pn P N           -> blocks get P / N
                            (P and N may be numbers OR placeholder strings)

Positional arguments are optional; anything omitted is asked for interactively
(when run in a terminal) or falls back to its default otherwise.

Examples
--------
  coplanar_magmom.py                                   # fully interactive
  coplanar_magmom.py POSCAR "[0,0,1]" Fe -M 3.0        # +3/-3 on Fe, c-axis planes
  coplanar_magmom.py POSCAR "[0,0,1]" "Fe Ni" -L 2 --pn 2.5 -1.5
  coplanar_magmom.py POSCAR "[0,0,1]" all --pn P N     # placeholder values

Outputs: MAGMOM, coplanar_atoms.txt, run_parameters.txt
"""
import sys
import argparse
from pathlib import Path
import numpy as np

GREEN = "\033[32m"
RESET = "\033[0m"


# ─────────────────────────────── POSCAR reader ──────────────────────────────
def read_poscar(fname):
    """Return (lattice 3x3 A, fractional coords Nx3, element list)."""
    txt = Path(fname).read_text().splitlines()
    scale = float(txt[1])
    lattice = np.array([[float(x) for x in ln.split()] for ln in txt[2:5]]) * scale
    symbols = txt[5].split()
    counts = list(map(int, txt[6].split()))
    natoms = sum(counts)

    ptr = 7
    if txt[ptr][0].lower() == "s":      # optional Selective dynamics line
        ptr += 1
    cartesian = txt[ptr][0].lower() in ("c", "k")
    ptr += 1                            # first coordinate line

    coords = np.array([[float(x) for x in txt[i].split()[:3]]
                       for i in range(ptr, ptr + natoms)])
    if cartesian:
        coords = coords @ np.linalg.inv(lattice)

    elements = np.repeat(symbols, counts)
    return lattice, coords, elements


# ─────────────────────────────── small helpers ──────────────────────────────
def ask(prompt, default=None, cast=str):
    tail = f" [{default}]" if default is not None else ""
    val = input(f"{prompt}{tail}: ").strip()
    return cast(val) if val else default


def parse_vector(vector_str):
    """Parse a '[X,Y,Z]' string into a numpy array."""
    s = vector_str.strip()
    if not (s.startswith("[") and s.endswith("]")):
        raise ValueError("vector must be in the form [X,Y,Z]")
    parts = [p.strip() for p in s[1:-1].split(",")]
    if len(parts) != 3:
        raise ValueError("vector must have exactly 3 components")
    try:
        return np.array([float(p) for p in parts])
    except ValueError:
        raise ValueError("vector components must be numbers")


def parse_atom_selection(atom_str, elems):
    """Turn an atom-selection string into a boolean mask over elems."""
    natoms = len(elems)
    if atom_str.strip().lower() == "all":
        return np.ones(natoms, bool)
    parts = atom_str.split()
    if all(p.lstrip("-").isdigit() for p in parts):     # 1-based indices
        mask = np.zeros(natoms, bool)
        mask[[int(x) - 1 for x in parts]] = True
        return mask
    keep = set(parts)                                   # element symbols
    return np.array([e in keep for e in elems])


def isatty():
    return sys.stdin.isatty()


# ─────────────────────────────── arg parsing ────────────────────────────────
def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="coplanar_magmom.py",
        description="Assign coplanar alternating MAGMOM values for VASP.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples")[1] if "Examples" in __doc__ else None,
    )
    p.add_argument("poscar", nargs="?", help="POSCAR/CONTCAR path")
    p.add_argument("vector", nargs="?", help="plane normal as [X,Y,Z]")
    p.add_argument("atoms", nargs="?",
                   help='atom selection: symbols ("Fe Ni"), 1-based indices, or "all"')
    p.add_argument("-t", "--tol", type=float, default=None,
                   help="coplanarity tolerance in A (default: 0.02)")
    p.add_argument("-L", "--layers", type=int, default=None,
                   help="planes per ferromagnetic block (default: 1)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("-M", "--moment", type=float, default=None,
                      help="moment magnitude; blocks become +M / -M")
    mode.add_argument("--pn", nargs="*", metavar=("P", "N"),
                      help="explicit positive/negative block values (2 values, "
                           "or none to be prompted)")
    return p.parse_args(argv)


def die(msg, code=1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


# ──────────────────────────────────── main ──────────────────────────────────
def main():
    a = parse_args(sys.argv[1:])

    # ---- POSCAR ----
    poscar = a.poscar
    if poscar is None:
        poscar = ask("Enter POSCAR file path") if isatty() else None
    if not poscar:
        die("a POSCAR file is required")
    if not Path(poscar).exists():
        die(f"POSCAR file not found: {poscar}")
    try:
        lattice, frac, elems = read_poscar(poscar)
    except Exception as e:                              # noqa: BLE001
        die(f"could not read POSCAR '{poscar}': {e}")
    natoms = len(elems)

    # ---- plane-normal vector ----
    if a.vector is not None:
        n_vec = parse_vector(a.vector)
    elif isatty():
        n_vec = parse_vector(ask("Plane-normal vector [X,Y,Z]", "[0,0,1]"))
    else:
        die("a plane-normal vector is required")

    # ---- atom selection ----
    print("\nElements present:", " ".join(sorted(set(elems))))
    if a.atoms is not None:
        atoms_str = a.atoms
    elif isatty():
        atoms_str = input("Atoms of interest (symbols OR indices; blank = all): ").strip() or "all"
    else:
        atoms_str = "all"
    try:
        mask = parse_atom_selection(atoms_str, elems)
    except Exception as e:                              # noqa: BLE001
        die(f"could not parse atom selection '{atoms_str}': {e}")
    if not mask.any():
        die("atom selection matched no atoms")

    # ---- tolerance & layers ----
    tol = a.tol if a.tol is not None else (float(ask("Coplanarity tolerance A", 0.02, float)) if isatty() else 0.02)
    L = a.layers if a.layers is not None else (int(ask("Layers per block L", 1, int)) if isatty() else 1)
    if tol <= 0:
        die("tolerance must be positive")
    if L < 1:
        die("layers per block must be >= 1")

    # ---- block-value mode ----
    if a.pn is not None:
        if len(a.pn) == 2:
            P, N = a.pn[0], a.pn[1]
        elif len(a.pn) == 0:
            P = ask("Positive-block value", "P")
            N = ask("Negative-block value", "N")
        else:
            die("--pn takes exactly two values (P and N)")
        mode = "pn"
    else:
        if a.moment is not None:
            M = a.moment
        elif isatty():
            M = float(ask("Magnetic-moment magnitude M", 1.0, float))
        else:
            M = 1.0
        mode = "moment"

    # ---- project atoms onto the normal and group into planes ----
    n_cart = n_vec @ lattice if np.all(np.abs(n_vec) <= 1) else n_vec
    n_hat = n_cart / np.linalg.norm(n_cart)
    proj = (frac @ lattice) @ n_hat

    planes = {}                                         # id -> [ref_proj, [atom_idx]]
    for i, p in enumerate(proj):
        if not mask[i]:
            continue
        pid = next((k for k, (ref, _) in planes.items() if abs(p - ref) < tol), None)
        if pid is None:
            pid = len(planes)
            planes[pid] = [p, []]
        planes[pid][1].append(i)
    ordered = sorted(planes.items(), key=lambda kv: kv[1][0])

    # ---- assign alternating values & build the MAGMOM list ----
    magmom = ["0"] * natoms
    table = []
    for plane_id, (_, idx_list) in enumerate(v[1] for v in ordered):
        positive = (plane_id // L) % 2 == 0
        if mode == "moment":
            value = f"{(M if positive else -M):+g}"
        else:
            value = str(P if positive else N)
        for idx in idx_list:
            magmom[idx] = value
            fc = " ".join(f"{x:.3f}" for x in frac[idx])
            table.append(f"{idx+1:<10d} {elems[idx]:<7} {plane_id:<8d} {value:<8} {fc}")

    # ---- write outputs ----
    Path("MAGMOM").write_text("MAGMOM = " + "  ".join(magmom) + "\n")
    print(f"\n{GREEN}Created MAGMOM with {natoms} entries.{RESET}")

    with open("coplanar_atoms.txt", "w") as f:
        f.write("atom_index element plane_ID magmom frac_coords\n")
        f.write("-" * 47 + "\n")
        f.write("\n".join(table) + "\n")
    print(f"{GREEN}Wrote plane assignment to coplanar_atoms.txt{RESET}")

    # canonical atom string for reproduction
    if mask.all():
        atoms_repr = "all"
    else:
        sel_elems = {elems[i] for i in range(natoms) if mask[i]}
        if np.array_equal(mask, np.array([e in sel_elems for e in elems])):
            atoms_repr = " ".join(sorted(sel_elems))
        else:
            atoms_repr = " ".join(str(i + 1) for i in range(natoms) if mask[i])
    vec_repr = f"[{n_vec[0]:g},{n_vec[1]:g},{n_vec[2]:g}]"
    mode_repr = f"-M {M:g}" if mode == "moment" else f"--pn {P} {N}"
    cmd = f'coplanar_magmom.py {poscar} "{vec_repr}" "{atoms_repr}" -t {tol:g} -L {L} {mode_repr}'

    with open("run_parameters.txt", "w") as f:
        f.write("# coplanar_magmom.py — reproduce this run with the command below\n")
        f.write(cmd + "\n\n")
        f.write(f"# POSCAR             : {poscar}\n")
        f.write(f"# plane normal       : {vec_repr}\n")
        f.write(f"# atoms              : {atoms_repr}\n")
        f.write(f"# tolerance (A)      : {tol:g}\n")
        f.write(f"# layers per block   : {L}\n")
        f.write(f"# block values       : {mode_repr}\n")
        f.write(f"# atoms processed    : {int(mask.sum())}/{natoms}\n")
        f.write(f"# planes found       : {len(ordered)}\n")
    print(f"{GREEN}Saved run parameters to run_parameters.txt{RESET}")

    print("\natom_index element plane_ID magmom frac_coords")
    print("-" * 47)
    print("\n".join(table))
    print(f"\n{len(ordered)} planes (tol={tol:g} A); values alternate every {L} plane(s).")
    print(f"Reproduce with:\n{cmd}")


if __name__ == "__main__":
    main()
