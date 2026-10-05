#!/usr/bin/env python3
"""Harvest QE vc-relax convergence sweeps into per-system tables.

Implements the pseudocode signed off 2026-07-10. If the root (default: the
current working directory) is itself a system directory — i.e. it directly
contains a sweep dir — only that system is harvested. Otherwise it walks every
system directory under the root. Either way it harvests
ecut_relax_sweep/ and kpt_relax_sweep/ (naming them explicitly is what skips
the *_fixed side tests), and writes four files into a convergence_data/
folder created at each system's top level:

    ecut_convergence.dat    kmesh_convergence.dat
    ecut_positions.dat      kmesh_positions.dat

A failed case (missing scf.out, or no "JOB DONE") keeps its row with N/A in
every field except the sweep parameter, and contributes no position rows.
Files are rebuilt whole on every run.

Usage:  python3 harvest_convergence.py [root_dir]
"""

import math
import re
import sys
from collections import Counter
from functools import reduce
from pathlib import Path

BOHR_TO_ANG = 0.529177210903

NA = "N/A"


# --- sweep parameter + nfu: always from scf.in (pseudocode 8-11) ---

def read_ecut(scf_in):
    m = re.search(r"ecutwfc\s*=\s*([0-9.+\-eEdD]+)", scf_in)
    return float(m.group(1).replace("d", "e").replace("D", "e"))


def read_kmesh(scf_in):
    lines = scf_in.splitlines()
    for i, line in enumerate(lines):
        if "K_POINTS" in line and "automatic" in line:
            return tuple(int(n) for n in lines[i + 1].split()[:3])
    raise ValueError("no 'K_POINTS automatic' card found")


ATOM_LINE = re.compile(r"^\s*([A-Z][a-z]?)\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+")


def read_atom_lines(text, start):
    """Atom (symbol, x, y, z) rows following the ATOMIC_POSITIONS line at start."""
    atoms = []
    for line in text.splitlines()[start + 1:]:
        m = ATOM_LINE.match(line)
        if not m:
            break
        sym, x, y, z = line.split()[:4]
        atoms.append((sym, float(x), float(y), float(z)))
    return atoms


def read_nfu(scf_in):
    lines = scf_in.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("ATOMIC_POSITIONS"))
    counts = Counter(sym for sym, *_ in read_atom_lines(scf_in, start))
    return reduce(math.gcd, counts.values())


# --- scf.out pieces ---

def last_energy(scf_out):
    """Last '!' line = final SCF at the relaxed cell (pseudocode 15)."""
    line = [l for l in scf_out.splitlines() if l.startswith("!")][-1]
    return float(re.search(r"=\s*([-\d.]+)\s*Ry", line).group(1))


def vec_len(v):
    return math.sqrt(sum(x * x for x in v))


def vec_angle(u, v):
    cosang = sum(a * b for a, b in zip(u, v)) / (vec_len(u) * vec_len(v))
    return math.degrees(math.acos(cosang))


def final_geometry(scf_out, path):
    """Cell + positions from the final-coordinates block (pseudocode 17-25).

    Returns (a, b, c, alpha, beta, gamma, atoms) with lengths in Angstrom,
    angles in degrees, atoms as (symbol, x, y, z) fractional.
    """
    m = re.search(r"Begin final coordinates(.*?)End final coordinates", scf_out, re.S)
    if not m:
        raise ValueError(f"{path}: JOB DONE but no final-coordinates block")
    block = m.group(1)

    hdr = re.search(r"CELL_PARAMETERS\s*\((angstrom|alat\s*=\s*[\d.]+)\)", block)
    if not hdr:
        raise ValueError(f"{path}: no CELL_PARAMETERS in final block")
    scale = 1.0
    if hdr.group(1) != "angstrom":
        alat = float(re.search(r"[\d.]+", hdr.group(1)).group())
        scale = alat * BOHR_TO_ANG
    lines = block[hdr.end():].splitlines()
    vecs = [[float(x) * scale for x in lines[i].split()] for i in (1, 2, 3)]

    a, b, c = (vec_len(v) for v in vecs)
    alpha = vec_angle(vecs[1], vecs[2])
    beta = vec_angle(vecs[0], vecs[2])
    gamma = vec_angle(vecs[0], vecs[1])

    pos_hdr = re.search(r"ATOMIC_POSITIONS\s*\((\w+)\)", block)
    if not pos_hdr or pos_hdr.group(1) != "crystal":
        unit = pos_hdr.group(1) if pos_hdr else "missing"
        raise ValueError(f"{path}: final ATOMIC_POSITIONS unit is '{unit}', expected 'crystal'")
    block_lines = block.splitlines()
    start = next(i for i, l in enumerate(block_lines) if "ATOMIC_POSITIONS" in l)
    atoms = read_atom_lines(block, start)
    return a, b, c, alpha, beta, gamma, atoms


def to_seconds(t):
    """'1h 2m 3.45s' (any subset, spaces optional) -> seconds."""
    total = 0.0
    for value, unit in re.findall(r"([\d.]+)\s*([hms])", t):
        total += float(value) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def timing(scf_out):
    """Cumulative timing block (pseudocode 26-28): total wall + per-SCF-cycle cost."""
    pwscf = re.search(r"^\s*PWSCF\s*:\s*(.*?)CPU\s*(.*?)WALL", scf_out, re.M)
    wall_s = to_seconds(pwscf.group(2))
    elec = re.search(r"^\s*electrons\s*:\s*(.*?)CPU.*?\(\s*(\d+)\s+calls\)", scf_out, re.M)
    scf_cycle_s = to_seconds(elec.group(1)) / int(elec.group(2))
    return wall_s, scf_cycle_s


# --- per-case harvest (pseudocode 7-30) ---

def harvest_case(case_dir, kind):
    """Returns (sort_key, param_fields, data_fields, pos_rows)."""
    scf_in = (case_dir / "scf.in").read_text()
    if kind == "ecut":
        ecut = read_ecut(scf_in)
        key, param = ecut, [f"{ecut:.1f}"]
    else:
        mesh = read_kmesh(scf_in)
        key, param = mesh[0] * mesh[1] * mesh[2], [str(n) for n in mesh]
    nfu = read_nfu(scf_in)

    out_path = case_dir / "scf.out"
    if not out_path.exists() or "JOB DONE" not in out_path.read_text():
        return key, param, [NA] * 10, []
    scf_out = out_path.read_text()

    e_ry = last_energy(scf_out)
    a, b, c, alpha, beta, gamma, atoms = final_geometry(scf_out, out_path)
    wall_s, scf_cycle_s = timing(scf_out)

    data = [f"{a:.6f}", f"{b:.6f}", f"{c:.6f}",
            f"{alpha:.4f}", f"{beta:.4f}", f"{gamma:.4f}",
            str(nfu), f"{e_ry:.8f}", f"{e_ry / nfu:.8f}",
            f"{wall_s:.2f}", f"{scf_cycle_s:.3f}"]
    pos = [param + [str(i), sym, f"{x:.9f}", f"{y:.9f}", f"{z:.9f}"]
           for i, (sym, x, y, z) in enumerate(atoms, start=1)]
    return key, param, data, pos


# --- output (pseudocode 31-34) ---

MAIN_COLS = ["a", "b", "c", "alpha", "beta", "gamma",
             "nfu", "E_ry", "E_ry_per_fu", "wall_s", "scf_cycle_s"]
POS_COLS = ["idx", "symbol", "x", "y", "z"]
PARAM_COLS = {"ecut": ["ecut"], "kmesh": ["nk1", "nk2", "nk3"]}


def write_table(path, header_cols, rows):
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0))
              for i, h in enumerate(header_cols)]
    lines = ["#  " + "  ".join(h.rjust(w) for h, w in zip(header_cols, widths))]
    lines += ["   " + "  ".join(f.rjust(w) for f, w in zip(row, widths)) for row in rows]
    path.write_text("\n".join(lines) + "\n")


def harvest_sweep(sys_dir, sweep_name, kind):
    sweep = sys_dir / sweep_name
    if not sweep.is_dir():
        return False
    cases = sorted(d for d in sweep.iterdir() if d.is_dir() and (d / "scf.in").exists())
    if not cases:
        return False

    results = sorted((harvest_case(d, kind) for d in cases), key=lambda r: r[0])
    main_rows = [param + data for _, param, data, _ in results]
    pos_rows = [row for _, _, _, pos in results for row in pos]

    out_dir = sys_dir / "convergence_data"
    out_dir.mkdir(exist_ok=True)
    write_table(out_dir / f"{kind}_convergence.dat",
                PARAM_COLS[kind] + MAIN_COLS, main_rows)
    write_table(out_dir / f"{kind}_positions.dat",
                PARAM_COLS[kind] + POS_COLS, pos_rows)
    n_na = sum(NA in row for row in main_rows)
    print(f"  {sys_dir.name}/{kind}: {len(main_rows)} cases"
          + (f" ({n_na} N/A)" if n_na else ""))
    return True


SWEEPS = (("ecut_relax_sweep", "ecut"), ("kpt_relax_sweep", "kmesh"))


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    # If root is itself a system dir (has a sweep dir), harvest just it;
    # otherwise treat its subdirectories as the system dirs.
    if any((root / sweep_name).is_dir() for sweep_name, _ in SWEEPS):
        system_dirs = [root]
    else:
        system_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    for sys_dir in system_dirs:
        for sweep_name, kind in SWEEPS:
            harvest_sweep(sys_dir, sweep_name, kind)


if __name__ == "__main__":
    main()
