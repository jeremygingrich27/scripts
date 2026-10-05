#!/usr/bin/env python3
"""gen_pp_slab.py — write pp.x / average.x inputs for vacuum-side charge-density
cuts and plane-averaged z-profiles of ONE finished slab calculation.

Implements the pseudocode signed off 2026-10-03 (with the amended step 4: the
cuts reuse one extracted density instead of re-extracting it).

Run on a case directory whose pw.x run has finished (CASE_DIR/scf.out must
exist; average.x's npt is the FFT grid along z read from it). The geometry is
the final coordinates in scf.out when it has them (relax / vc-relax), else
scf.in (plain scf). Writes, under CASE_DIR/<outdir>/:

    profiles/rho/pp.in, average.in        plot_num=0  -> 3D cube + rho(z)
    profiles/vbare_h/pp.in, average.in    plot_num=11 -> cube + V(z)
    cuts/<face>_<element>/h<h>A/pp.in     2D xy plane at height h above a face
    run_pp.sh                             runs them all in the right order

The cuts read the density extracted once by profiles/rho (blank &INPUTPP,
&PLOT filepp), so run_pp.sh runs profiles/rho first.

--spin-density (amendment signed off 2026-10-05; nspin=2 only) adds
profiles/magn (plot_num=6, rho_up - rho_down) and a pp_magn.in -> cut_magn.dat
next to each cut, reading profiles/magn/magn.

Scope: ibrav=0, CELL_PARAMETERS in angstrom with a3 along z (slab normal = z),
ATOMIC_POSITIONS in crystal. The in-plane plotting window must be orthogonal
(pp.x requires e1 ⟂ e2): a1 ⟂ a2 uses (a1, a2); a hexagonal cell
(|a1| = |a2|, 120 deg) uses the a x sqrt3 a rectangle (a1+a2, a2-a1).

    gen_pp_slab.py CASE_DIR --awin-ang 2.531 [--heights "1 2 3 4 5 6"]
                   [--nx 100 --ny 173] [--structure scf.in|scf.out] [--outdir pp]
"""

import argparse
import math
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import make_deposition as md
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import make_deposition as md

BOHR_TO_ANG = 0.529177210903


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def final_positions(out):
    """Crystal positions from the 'Begin final coordinates' block of a relax /
    vc-relax output, or None if the run has no such block (plain scf)."""
    if "Begin final coordinates" not in out:
        return None
    tail = out.split("Begin final coordinates", 1)[1].split("End final coordinates", 1)[0]
    pm = re.search(r"(?i)ATOMIC_POSITIONS\s*\(([^)]*)\)", tail)
    if not pm or "crystal" not in pm.group(1).lower():
        raise ValueError("final ATOMIC_POSITIONS are not in crystal units")
    atoms = []
    for line in tail[pm.end():].strip().splitlines():
        parts = line.split()
        if len(parts) < 4 or not re.match(r"[A-Za-z]", parts[0]):
            break
        atoms.append((parts[0], [float(p) for p in parts[1:4]]))
    return atoms


def fft_nz(out):
    """Dense-grid FFT dimension along z, from the first 'FFT dimensions' line."""
    m = re.search(r"FFT dimensions:\s*\(\s*(\d+),\s*(\d+),\s*(\d+)\)", out)
    if not m:
        raise ValueError("no 'FFT dimensions' line in scf.out")
    return int(m.group(3))


def plot_window(a1, a2):
    """Orthogonal in-plane (e1, e2) in angstrom, as pp.x requires."""
    if abs(_dot(a1, a2)) < 1e-6 * _norm(a1) * _norm(a2):
        return a1, a2
    cosg = _dot(a1, a2) / (_norm(a1) * _norm(a2))
    if abs(_norm(a1) - _norm(a2)) < 1e-6 and abs(cosg + 0.5) < 1e-6:
        return ([x + y for x, y in zip(a1, a2)], [y - x for x, y in zip(a1, a2)])
    raise ValueError("in-plane cell is neither rectangular nor hexagonal (120 deg)")


def _vec(name, v):
    return ", ".join(f"{name}({i + 1}) = {x:.10f}" for i, x in enumerate(v))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("case_dir", help="slab case dir holding scf.in and a finished scf.out")
    p.add_argument("--awin-ang", type=float, required=True,
                   help="average.x macroscopic-average window in angstrom "
                        "(e.g. one bulk layer period); converted to bohr")
    p.add_argument("--heights", default="1 2 3 4 5 6",
                   help='cut heights in angstrom above each face (default "1 2 3 4 5 6")')
    p.add_argument("--nx", type=int, default=100, help="points along e1 (default 100)")
    p.add_argument("--ny", type=int, default=173, help="points along e2 (default 173)")
    p.add_argument("--structure", choices=["scf.in", "scf.out"], default=None,
                   help="force the geometry source (default: scf.out final "
                        "coordinates if present, else scf.in)")
    p.add_argument("--outdir", default="pp", help="output folder inside CASE_DIR (default pp)")
    p.add_argument("--spin-density", action="store_true",
                   help="also the spin polarization (plot_num=6): profile + cuts (needs nspin=2)")
    args = p.parse_args(argv)

    case = args.case_dir
    text = qi.read_input(os.path.join(case, "scf.in"))
    out_path = os.path.join(case, "scf.out")
    if not os.path.isfile(out_path):
        sys.exit(f"{out_path} not found: run the SCF first (npt is read from it)")
    out = open(out_path).read()
    if "JOB DONE" not in out:
        sys.exit(f"{out_path} has no JOB DONE: the run did not finish")

    # 1. geometry
    lines = text.splitlines()
    _i, cell_unit = qi._find_cell(lines)
    if "angstrom" not in (cell_unit or "").lower():
        sys.exit("CELL_PARAMETERS must be in angstrom")
    a1, a2, a3 = qi.get_cell(text)
    if abs(a3[0]) > 1e-8 or abs(a3[1]) > 1e-8:
        sys.exit("a3 is not along z: slab normal must be z")
    c = a3[2]
    alat = _norm(a1)
    prefix = qi.get_key(text, "prefix").strip("'\"")
    relaxed = final_positions(out)
    if args.structure == "scf.out" and relaxed is None:
        sys.exit("--structure scf.out, but scf.out has no final coordinates")
    if relaxed is not None and args.structure != "scf.in":
        atoms, source = relaxed, "scf.out (final coordinates)"
    else:
        unit, rows = md.get_atoms(text)
        if unit != "crystal":
            sys.exit("ATOMIC_POSITIONS must be in crystal units")
        atoms, source = [(lab, xyz) for lab, xyz, _flags in rows], "scf.in"

    # 2. in-plane orthogonal window, in alat units
    e1, e2 = plot_window(a1, a2)
    e1a, e2a = [x / alat for x in e1], [x / alat for x in e2]

    # 3. faces
    zs = [((f[2] % 1.0) * c, re.sub(r"\d+$", "", lab)) for lab, f in atoms]
    z_top = max(z for z, _ in zs)
    z_bot = min(z for z, _ in zs)
    # every element in the outermost plane (within 0.1 A), e.g. "N-Sc" for rocksalt
    el_top = "-".join(sorted({el for z, el in zs if z_top - z < 0.1}))
    el_bot = "-".join(sorted({el for z, el in zs if z - z_bot < 0.1}))
    vac = c - (z_top - z_bot)
    mid_vac = (z_top + (z_bot + c)) / 2.0                     # in [z_top, z_bot + c]
    sawtooth = None
    if (qi.get_key(text, "tefield") or "").lower().strip(".") in ("true", "t"):
        emax = float(qi.get_key(text, "emaxpos"))
        eop = float(qi.get_key(text, "eopreg"))
        sawtooth = (emax * c, (emax + eop) * c)              # may extend past c

    def in_sawtooth(z):
        if sawtooth is None:
            return False
        lo, hi = sawtooth
        return any(lo <= z + k * c <= hi for k in (-1, 0, 1))

    nz = fft_nz(out)
    nspin = (qi.get_key(text, "nspin") or "1").strip()
    if args.spin_density and nspin != "2":
        sys.exit("--spin-density needs an nspin=2 calculation")
    heights = [float(h) for h in args.heights.split()]
    base = os.path.join(case, args.outdir)
    warnings = []

    # 5. profiles (rho first: the cuts read its extracted density)
    awin_bohr = args.awin_ang / BOHR_TO_ANG
    profiles = [("rho", 0), ("vbare_h", 11)] + ([("magn", 6)] if args.spin_density else [])
    for sub, plot_num in profiles:
        d = os.path.join(base, "profiles", sub)
        write(os.path.join(d, "pp.in"),
              f"&inputpp\n  prefix = '{prefix}'\n  plot_num = {plot_num}\n"
              f"  filplot = '{sub}'\n/\n"
              f"&plot\n  iflag = 3\n  output_format = 6\n  fileout = '{sub}.cube'\n/\n")
        write(os.path.join(d, "average.in"),
              f"1\n{sub}\n1.0\n{nz}\n3\n{awin_bohr:.6f}\n")

    # 4'. cuts, reusing profiles/rho/rho
    cut_dirs = []
    for face, z0, el, sign in (("top", z_top, el_top, +1), ("bottom", z_bot, el_bot, -1)):
        for h in heights:
            z = (z0 + sign * h) % c
            zun = z0 + sign * h                               # unwrapped, for checks
            beyond_mid = (zun > mid_vac) if sign > 0 else (zun + c < mid_vac)
            if in_sawtooth(z):
                warnings.append(f"{face} h={h:g} A: z={z:.3f} A is inside the dipole sawtooth region")
            if beyond_mid:
                warnings.append(f"{face} h={h:g} A: past mid-vacuum (closer to the other face)")
            rel = os.path.join("cuts", f"{face}_{el}", f"h{h:g}A")
            x0 = [0.0, 0.0, z / alat]
            write(os.path.join(base, rel, "pp.in"),
                  "&inputpp\n/\n"
                  "&plot\n  nfile = 1\n  filepp(1) = '../../../profiles/rho/rho'\n"
                  "  weight(1) = 1.0\n  iflag = 2\n  output_format = 7\n"
                  "  fileout = 'cut.dat'\n"
                  f"  {_vec('e1', e1a)}\n  {_vec('e2', e2a)}\n  {_vec('x0', x0)}\n"
                  f"  nx = {args.nx}, ny = {args.ny}\n/\n")
            if args.spin_density:
                write(os.path.join(base, rel, "pp_magn.in"),
                      "&inputpp\n/\n"
                      "&plot\n  nfile = 1\n  filepp(1) = '../../../profiles/magn/magn'\n"
                      "  weight(1) = 1.0\n  iflag = 2\n  output_format = 7\n"
                      "  fileout = 'cut_magn.dat'\n"
                      f"  {_vec('e1', e1a)}\n  {_vec('e2', e2a)}\n  {_vec('x0', x0)}\n"
                      f"  nx = {args.nx}, ny = {args.ny}\n/\n")
            cut_dirs.append((rel, face, h, z))

    # runner
    run = ["#!/bin/bash",
           "# run_pp.sh — written by gen_pp_slab.py. Runs pp.x / average.x in order.",
           "# ESPRESSO_TMPDIR must point at the SCF's temp dir (where <prefix>.save is).",
           "# Override the launchers with PPX / AVGX if needed.",
           "set -uo pipefail",
           ': "${ESPRESSO_TMPDIR:?set ESPRESSO_TMPDIR to the SCF temp dir first}"',
           'PPX="${PPX:-ibrun pp.x}"',
           'AVGX="${AVGX:-average.x}"',
           'HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
           ""]
    for sub, _pn in profiles:
        run += [f'( cd "$HERE/profiles/{sub}" && $PPX < pp.in > pp.out && '
                f'$AVGX < average.in > average.out )']
        if sub == "rho":
            run += ['[ -f "$HERE/profiles/rho/rho" ] || { echo "rho extraction failed"; exit 1; }']
    for rel, _f, _h, _z in cut_dirs:
        run.append(f'( cd "$HERE/{rel}" && $PPX < pp.in > pp.out )')
    if args.spin_density:
        for rel, _f, _h, _z in cut_dirs:
            run.append(f'( cd "$HERE/{rel}" && $PPX < pp_magn.in > pp_magn.out )')
    run.append('echo "run_pp.sh done."')
    write(os.path.join(base, "run_pp.sh"), "\n".join(run) + "\n")
    os.chmod(os.path.join(base, "run_pp.sh"), 0o775)

    # 6. summary
    print(f"case        {case}   prefix '{prefix}'   geometry from {source}")
    print(f"alat        {alat:.6f} A   cell c {c:.4f} A   FFT nz {nz}")
    print(f"window      e1 = {[round(x, 6) for x in e1a]}  e2 = {[round(x, 6) for x in e2a]} (alat)"
          f"   = {_norm(e1):.4f} x {_norm(e2):.4f} A, {args.nx} x {args.ny} points")
    print(f"faces       top {el_top} z = {z_top:.4f} A   bottom {el_bot} z = {z_bot:.4f} A   vacuum {vac:.3f} A")
    if sawtooth:
        print(f"sawtooth    z = {sawtooth[0]:.3f} .. {sawtooth[1]:.3f} A (mod c)")
    print(f"awin        {args.awin_ang} A = {awin_bohr:.4f} bohr")
    for rel, face, h, z in cut_dirs:
        print(f"  {rel:28s} z = {z:8.4f} A  (x0_z = {z / alat:.6f} alat)")
    for w in warnings:
        print("WARNING:", w)
    print(f"wrote {base}/ (run_pp.sh runs everything in order)")


if __name__ == "__main__":
    main()
