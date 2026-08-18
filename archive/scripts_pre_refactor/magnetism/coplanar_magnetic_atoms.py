#!/usr/bin/env python3
"""
coplanar_magnetic_atoms.py
Identify coplanar magnetic atoms for a user‑supplied subset of atoms in a POSCAR /
CONTCAR and assign ± magnetic signs in blocks of L planes.

Inputs
-------
coplanar_magnetic_atoms.py [POSCAR FILE] [ORTHOGONAL VECTOR] [ATOMS] [TOLERANCE] [LAYERS] [MAGNITUDE]

Where:
- POSCAR FILE: Path to POSCAR/CONTCAR file
- ORTHOGONAL VECTOR: Vector in format [X,Y,Z] (e.g., [1,0,0] or [0.5,0.5,0])
- ATOMS: Atom selection - element symbols (e.g., "Fe Ni") or indices (e.g., "1 2 3") or "all"
- TOLERANCE: Coplanarity tolerance in Å (default: 0.02)
- LAYERS: Layers per ferromagnetic block L (default: 1)
- MAGNITUDE: Magnetic moment magnitude M (default: 1)

If no arguments are provided, the script will prompt interactively for inputs.
Arguments can be provided partially - missing arguments will be prompted interactively.

Outputs
-------
• MAGMOM  – line suitable for VASP INCAR
• coplanar_atoms.txt – detailed table of plane assignment
"""
import sys, numpy as np
from pathlib import Path
import re

# Terminal colors
GREEN = "\033[32m"
RESET = "\033[0m"

# ─────────────────────────────────── POSCAR reader ───────────────────────────
def read_poscar(fname):
    """Return (lattice 3×3 Å, fractional coords N×3, element list)"""
    txt = Path(fname).read_text().splitlines()
    scale   = float(txt[1])
    lattice = np.array([[float(x) for x in ln.split()] for ln in txt[2:5]]) * scale
    symbols = txt[5].split()
    counts  = list(map(int, txt[6].split()))
    natoms  = sum(counts)

    ptr = 7
    if txt[ptr][0].lower() == 's':   # Selective dynamics line
        ptr += 1
    cartesian = txt[ptr][0].lower() in ('c', 'k')
    ptr += 1                         # now at first coord line

    coords = np.array([[float(x) for x in txt[i].split()[:3]]
                       for i in range(ptr, ptr + natoms)])
    if cartesian:
        coords = coords @ np.linalg.inv(lattice)

    elements = np.repeat(symbols, counts)
    return lattice, coords, elements

# ─────────────────────────────────── helper -----------------------------------
def ask(prompt, default=None, cast=str):
    tail = f" [{default}]" if default is not None else ""
    val  = input(f"{prompt}{tail}: ").strip()
    return cast(val) if val else default

def parse_vector(vector_str):
    """Parse vector string in format [X,Y,Z] and return numpy array"""
    # Remove any whitespace
    vector_str = vector_str.strip()
    
    # Check if it's in [X,Y,Z] format
    if not (vector_str.startswith('[') and vector_str.endswith(']')):
        raise ValueError("Vector must be in format [X,Y,Z]")
    
    # Extract the content inside brackets
    content = vector_str[1:-1]
    
    # Split by comma and convert to floats
    try:
        components = [float(x.strip()) for x in content.split(',')]
        if len(components) != 3:
            raise ValueError("Vector must have exactly 3 components")
        return np.array(components)
    except ValueError as e:
        if "could not convert" in str(e):
            raise ValueError("Vector components must be numbers")
        raise

def get_poscar_file():
    """Interactively get POSCAR file path"""
    while True:
        fname = input("Enter POSCAR file path: ").strip()
        if not fname:
            print("Please provide a file path.")
            continue
        
        path = Path(fname)
        if not path.exists():
            print(f"File '{fname}' not found. Please check the path.")
            continue
        
        try:
            # Try to read the file to validate it's a proper POSCAR
            read_poscar(fname)
            return fname
        except Exception as e:
            print(f"Error reading POSCAR file: {e}")
            continue

def get_orthogonal_vector():
    """Interactively get orthogonal vector"""
    while True:
        vector_str = input("Enter orthogonal vector in format [X,Y,Z] (e.g., [1,0,0]): ").strip()
        if not vector_str:
            print("Please provide a vector.")
            continue
        
        try:
            return parse_vector(vector_str)
        except ValueError as e:
            print(f"Error: {e}")
            continue

def parse_atom_selection(atom_str, elems):
    """Parse atom selection string and return boolean mask"""
    natoms = len(elems)
    
    if atom_str.lower() == "all":
        return np.ones(natoms, bool)
    
    # Check if it's indices (all numeric)
    parts = atom_str.split()
    if all(part.isdigit() for part in parts):
        idx = [int(x)-1 for x in parts]
        mask = np.zeros(natoms, bool)
        mask[idx] = True
        return mask
    
    # Otherwise treat as element symbols
    keep = set(parts)
    return np.array([e in keep for e in elems])

# ─────────────────────────────────── main -------------------------------------
def main():
    # Parse command line arguments
    args = sys.argv[1:]
    
    # Initialize variables
    poscar = None
    n_vec = None
    atoms = None
    tol = None
    L = None
    M = None
    
    # Parse arguments if provided
    if len(args) >= 1:
        poscar = args[0]
        if not Path(poscar).exists():
            print(f"Error: POSCAR file '{poscar}' not found.")
            sys.exit(1)
    
    if len(args) >= 2:
        try:
            n_vec = parse_vector(args[1])
        except ValueError as e:
            print(f"Error parsing orthogonal vector: {e}")
            print("Vector must be in format [X,Y,Z], e.g., [1,0,0] or [0.5,0.5,0]")
            sys.exit(1)
    
    if len(args) >= 3:
        atoms = args[2]
    
    if len(args) >= 4:
        try:
            tol = float(args[3])
        except ValueError:
            print(f"Error: Tolerance must be a number, got '{args[3]}'")
            sys.exit(1)
    
    if len(args) >= 5:
        try:
            L = int(args[4])
        except ValueError:
            print(f"Error: Layers must be an integer, got '{args[4]}'")
            sys.exit(1)
    
    if len(args) >= 6:
        try:
            M = float(args[5])
        except ValueError:
            print(f"Error: Magnitude must be a number, got '{args[5]}'")
            sys.exit(1)
    
    if len(args) > 6:
        print("Too many arguments provided.")
        print(__doc__)
        sys.exit(1)
    
    # Get missing arguments interactively
    if poscar is None:
        print("Interactive mode - please provide the following inputs:")
        poscar = get_poscar_file()
    
    if n_vec is None:
        n_vec = get_orthogonal_vector()
    
    # Read POSCAR file
    try:
        lattice, frac, elems = read_poscar(poscar)
    except Exception as e:
        print(f"Error reading POSCAR file: {e}")
        sys.exit(1)
    
    natoms = len(elems)
    
    # ---- choose atoms --------------------------------------------------------
    print("\nElements present:", " ".join(sorted(set(elems))))
    
    if atoms is None:
        sel = input("Atoms of interest (symbols OR indices; blank = all): ").split()
        if not sel:
            mask = np.ones(natoms, bool)
        elif sel[0].isdigit():
            idx  = [int(x)-1 for x in sel]
            mask = np.zeros(natoms, bool); mask[idx] = True
        else:
            keep = set(sel); mask = np.array([e in keep for e in elems])
    else:
        try:
            mask = parse_atom_selection(atoms, elems)
        except Exception as e:
            print(f"Error parsing atom selection: {e}")
            sys.exit(1)
    
    if tol is None:
        tol = float(ask("Coplanarity tolerance Å", 0.02, float))
    
    if L is None:
        L = int(ask("Layers per ferromagnetic block L", 1, int))
    
    if M is None:
        M = float(ask("Magnetic‑moment magnitude M", 1, float))

    # ---- projections ---------------------------------------------------------
    n_cart = n_vec @ lattice if np.all(np.abs(n_vec) <= 1) else n_vec
    n_hat  = n_cart / np.linalg.norm(n_cart)
    cart   = frac @ lattice
    proj   = cart @ n_hat

    planes = {}                                # plane_id → [ref_proj, [atom_idx]]
    for i, p in enumerate(proj):
        if not mask[i]:
            continue
        pid = next((k for k,(ref,_) in planes.items() if abs(p-ref)<tol), None)
        if pid is None:
            pid = len(planes); planes[pid] = [p, []]
        planes[pid][1].append(i)

    ordered = sorted(planes.items(), key=lambda kv: kv[1][0])

    # ---- assign signs & build MAGMOM array -----------------------------------
    magmom_values = np.zeros(natoms)
    table_lines   = []
    for plane_id, (_, idx_list) in enumerate(a[1] for a in ordered):
        sign = +1 if (plane_id//L)%2 == 0 else -1
        for idx in idx_list:
            magmom_values[idx] = sign * M
            fc = " ".join(f"{x:.3f}" for x in frac[idx])
            table_lines.append(f"{idx+1:<10d} {elems[idx]:<7} {plane_id:<8d} {sign:+d}   {fc}")

    # ---- write MAGMOM file ---------------------------------------------------
    with open("MAGMOM", "w") as f:
        line = "MAGMOM = " + "  ".join(f"{v:+g}" for v in magmom_values)
        f.write(line + "\n")
    print(f"\n{GREEN}Created MAGMOM file with {natoms} entries.{RESET}")

    # ---- write detailed table ------------------------------------------------
    with open("coplanar_atoms.txt", "w") as f:
        f.write("atom_index element plane_ID sign frac_coords\n")
        f.write("---------------------------------------------\n")
        f.write("\n".join(table_lines) + "\n")
    print(f"{GREEN}Wrote detailed plane assignment to coplanar_atoms.txt{RESET}")

    # ---- save input parameters for reproducibility ---------------------------
    # Format atoms selection for command line
    selected_atoms = []
    if np.all(mask):
        atoms_str = "all"
    else:
        # Check if selection matches element-based selection
        selected_elements = set()
        for i, selected in enumerate(mask):
            if selected:
                selected_elements.add(elems[i])
        
        # If all atoms of certain elements are selected, use element names
        element_mask = np.array([e in selected_elements for e in elems])
        if np.array_equal(mask, element_mask):
            atoms_str = " ".join(sorted(selected_elements))
        else:
            # Otherwise use indices
            indices = [str(i+1) for i, selected in enumerate(mask) if selected]
            atoms_str = " ".join(indices)
    
    # Format vector as [X,Y,Z]
    vector_str = f"[{n_vec[0]},{n_vec[1]},{n_vec[2]}]"
    
    # Create command line
    cmd_line = f"./coplanar_magnetic_atoms.py {poscar} {vector_str} \"{atoms_str}\" {tol} {L} {M}"
    
    with open("run_parameters.txt", "w") as f:
        f.write("# Coplanar Magnetic Atoms - Run Parameters\n")
        f.write("# This file contains the exact command line arguments used\n")
        f.write("# You can reproduce this run by copying the command below\n")
        f.write("#\n")
        f.write("# Command line:\n")
        f.write(f"{cmd_line}\n")
        f.write("#\n")
        f.write("# Parameters breakdown:\n")
        f.write(f"# POSCAR file: {poscar}\n")
        f.write(f"# Orthogonal vector: {vector_str}\n")
        f.write(f"# Atoms: {atoms_str}\n")
        f.write(f"# Tolerance: {tol} Å\n")
        f.write(f"# Layers per block: {L}\n")
        f.write(f"# Magnetic moment magnitude: {M}\n")
        f.write(f"# Total atoms processed: {np.sum(mask)}/{natoms}\n")
        f.write(f"# Planes found: {len(ordered)}\n")
    
    print(f"{GREEN}Saved run parameters to run_parameters.txt{RESET}")

    # ---- also echo table to stdout ------------------------------------------
    print("\natom_index element plane_ID sign frac_coords")
    print("---------------------------------------------")
    print("\n".join(table_lines))
    print(f"\n{len(ordered)} planes found (tol={tol} Å). "
          f"Sign repeats every {L} plane(s).  M = {M}")
    print(f"\nTo reproduce this run, use:")
    print(f"{cmd_line}")

# ------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
