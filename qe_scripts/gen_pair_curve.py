#!/usr/bin/env python3
"""gen_pair_curve.py — write pw.x scf inputs for an interaction-energy curve of
two atoms or two rigid molecules in a vacuum box, one input per separation, or
a single isolated-atom reference in the same box.

Implements the pseudocode signed off 2026-10-03 (plus the single-atom reference
mode asked for in the same round). Generates inputs only: no running,
harvesting or plotting.

    gen_pair_curve.py --pair Sc,N --pseudos DIR --grid "0.8:3.0:0.05,3.0:12.0:0.25"
    gen_pair_curve.py --molecule N2 --bond 1.11 --orientation parallel --pseudos DIR --grid ...
    gen_pair_curve.py --atom Sc --pseudos DIR

Geometry (cartesian angstrom, orthorhombic box L x W x H, pair axis = x):
  atom pair:     A at (L/2 - d/2, W/2, H/2), B at (L/2 + d/2, W/2, H/2)
  molecule pair: centres at L/2 -/+ d/2; each bond (--bond) along y
                 (parallel) or along x (collinear)
  single atom:   at the box centre
A separation is skipped (with a warning) if two atoms would be closer than
0.8 A, or if the motif leaves less than 9 A of vacuum to its image along x.

Every input: calculation='scf', nspin=2, starting_magnetization = --start-mag
on every species, gaussian smearing, a single Gamma point written as
`K_POINTS automatic 1 1 1 0 0 0`, pseudo_dir = absolute path of --pseudos
(generate on the machine that runs them).

Why not `K_POINTS gamma`: QE 7.3 stops in orthoUwfc ("Gamma-only calculation
for this case not implemented") when ortho-atomic Hubbard projectors meet the
Gamma-only trick (found 2026-10-03 on the Sc-N dev test). 1 1 1 is the same
k-point with complex wavefunctions (~2x cost); used for every curve so all are
computed the same way. A HUBBARD card is
added only if --hubbard is given and its element is present.

Spin starts (amendment signed off 2026-10-03): --spin-starts takes
"parallel", "antiparallel" or both. parallel: every atom +start-mag.
antiparallel: atom B (or molecule B) gets -start-mag; when both partners are
the same element, B becomes its own species "<El>1" with the same .upf (and the
HUBBARD card covers it). Run both and keep the lower energy at each separation.
--electron-maxstep is written to &electrons when given.

Layout: OUTDIR/<name>/<parallel|antiparallel>/d_<sep>A/scf.in
        (name: Sc-N, Sc-Sc, N-N, N2-N2_parallel, N2-N2_collinear)
        or OUTDIR/atom_<X>/scf.in
"""

import argparse
import math
import os
import re
import sys

MASSES = {"H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "Si": 28.086,
          "Sc": 44.955908, "Ga": 69.723, "Al": 26.982}
MOLECULES = {"N2": ("N", "N")}
MIN_DIST = 0.8      # A, closest allowed approach of any two atoms
MIN_GAP = 9.0       # A, minimum vacuum between the motif and its image along x


def parse_grid(spec):
    """'0.8:3.0:0.05,3.0:12.0:0.25' -> sorted unique separations (3 decimals)."""
    seps = set()
    for seg in spec.split(","):
        start, stop, step = (float(x) for x in seg.split(":"))
        n = int(round((stop - start) / step))
        for i in range(n + 1):
            seps.add(round(start + i * step, 3))
    return sorted(seps)


def element(label):
    return re.sub(r"\d+$", "", label)


def motif(args, d, L, W, H, start="parallel"):
    """List of (species label, [x, y, z], spin sign) for one separation d.
    antiparallel: partner B gets sign -1; a same-element partner is relabelled
    '<El>1' so it can carry its own starting_magnetization."""
    cx, cy, cz = L / 2.0, W / 2.0, H / 2.0
    anti = start == "antiparallel"
    if args.atom:
        return [(args.atom, [cx, cy, cz], 1)]
    if args.pair:
        a, b = args.pair
        lb = b + "1" if (anti and a == b) else b
        return [(a, [cx - d / 2, cy, cz], 1), (lb, [cx + d / 2, cy, cz], -1 if anti else 1)]
    el1, el2 = MOLECULES[args.molecule]
    half = args.bond / 2.0
    out = []
    for m, cxm in enumerate((cx - d / 2, cx + d / 2)):
        sign = -1 if (anti and m == 1) else 1
        l1, l2 = (el1 + "1", el2 + "1") if (anti and m == 1) else (el1, el2)
        if args.orientation == "parallel":
            out += [(l1, [cxm, cy - half, cz], sign), (l2, [cxm, cy + half, cz], sign)]
        else:
            out += [(l1, [cxm - half, cy, cz], sign), (l2, [cxm + half, cy, cz], sign)]
    return out


def closest(atoms):
    best = float("inf")
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            best = min(best, math.dist(atoms[i][1], atoms[j][1]))
    return best


def deck(args, atoms, L, W, H, pseudo_abs):
    species = sorted({lab for lab, _p, _s in atoms})
    sign = {lab: s for lab, _p, s in atoms}
    lines = ["&control", "  calculation = 'scf'", "  prefix = 'pair'",
             f"  pseudo_dir = '{pseudo_abs}'", "/",
             "&system", "  ibrav = 0", f"  nat = {len(atoms)}", f"  ntyp = {len(species)}",
             f"  ecutwfc = {args.ecut}", "  nspin = 2"]
    for i, lab in enumerate(species):
        lines.append(f"  starting_magnetization({i + 1}) = {sign[lab] * args.start_mag}")
    lines += ["  occupations = 'smearing'", "  smearing = 'gaussian'",
              f"  degauss = {args.degauss}", "/",
              "&electrons", f"  conv_thr = {args.conv_thr}",
              f"  mixing_beta = {args.mixing_beta}"]
    if args.electron_maxstep:
        lines.append(f"  electron_maxstep = {args.electron_maxstep}")
    lines += ["/", "ATOMIC_SPECIES"]
    for lab in species:
        lines.append(f"  {lab:<3} {MASSES[element(lab)]}  {element(lab)}.upf")
    lines.append("ATOMIC_POSITIONS (angstrom)")
    for lab, (x, y, z), _s in atoms:
        lines.append(f"  {lab:<3} {x:.6f}  {y:.6f}  {z:.6f}")
    lines += ["CELL_PARAMETERS (angstrom)", f"  {L:.6f}  0.000000  0.000000",
              f"  0.000000  {W:.6f}  0.000000", f"  0.000000  0.000000  {H:.6f}",
              "K_POINTS automatic", "  1 1 1 0 0 0"]
    if args.hubbard:
        label, value, proj = args.hubbard.split()
        hel, shell = label.split("-")
        hub = [lab for lab in species if element(lab) == hel]
        if hub:
            lines.append(f"HUBBARD ({proj})")
            lines += [f"U {lab}-{shell} {value}" for lab in hub]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--pair", help="two atoms, e.g. Sc,N")
    what.add_argument("--molecule", choices=sorted(MOLECULES), help="two rigid molecules")
    what.add_argument("--atom", help="single isolated-atom reference, e.g. Sc")
    p.add_argument("--bond", type=float, help="molecule bond length in A (with --molecule)")
    p.add_argument("--orientation", choices=["parallel", "collinear"],
                   help="molecule bonds perpendicular (parallel) or along (collinear) the axis")
    p.add_argument("--pseudos", required=True, help="dir holding <El>.upf")
    p.add_argument("--grid", help='separations "start:stop:step,..." in A (not with --atom)')
    p.add_argument("--box", default="30 20 20", help='box L W H in A (default "30 20 20")')
    p.add_argument("--ecut", type=float, default=100.0, help="ecutwfc in Ry (default 100)")
    p.add_argument("--degauss", type=float, default=0.01, help="gaussian smearing in Ry (default 0.01)")
    p.add_argument("--start-mag", type=float, default=0.5, help="starting_magnetization (default 0.5)")
    p.add_argument("--conv-thr", default="1.0e-8", help="conv_thr (default 1.0e-8)")
    p.add_argument("--mixing-beta", default="0.4", help="mixing_beta (default 0.4)")
    p.add_argument("--hubbard", help='e.g. "Sc-3d 5.0 ortho-atomic" (added only if Sc is present)')
    p.add_argument("--electron-maxstep", type=int, help="&electrons electron_maxstep (QE default 100)")
    p.add_argument("--spin-starts", default="parallel",
                   help='"parallel", "antiparallel" or "parallel,antiparallel" (default parallel)')
    p.add_argument("--outdir", default=".", help="parent output dir (default .)")
    args = p.parse_args(argv)

    if args.pair:
        args.pair = [x.strip() for x in args.pair.split(",")]
        if len(args.pair) != 2:
            sys.exit("--pair needs exactly two elements, e.g. Sc,N")
    if args.molecule and (args.bond is None or args.orientation is None):
        sys.exit("--molecule needs --bond and --orientation")
    if not args.atom and not args.grid:
        sys.exit("--grid is required for --pair / --molecule")
    L, W, H = (float(x) for x in args.box.split())
    pseudo_abs = os.path.abspath(args.pseudos)

    if args.atom:
        name, seps = f"atom_{args.atom}", [None]
    elif args.pair:
        name, seps = "-".join(args.pair), parse_grid(args.grid)
    else:
        name, seps = f"{args.molecule}-{args.molecule}_{args.orientation}", parse_grid(args.grid)

    starts = [None] if args.atom else [x.strip() for x in args.spin_starts.split(",")]
    for st in starts:
        if st not in (None, "parallel", "antiparallel"):
            sys.exit(f"unknown spin start {st!r}")
    elements = {element(lab) for lab, _p, _s in motif(args, 1.0 if seps[0] is None else seps[0], L, W, H)}
    for el in elements:
        if el not in MASSES:
            sys.exit(f"no mass for {el}: add it to MASSES")
        if not os.path.isfile(os.path.join(pseudo_abs, f"{el}.upf")):
            sys.exit(f"{el}.upf not found in {pseudo_abs}")

    written, skipped = 0, []
    for st in starts:
        for d in seps:
            atoms = motif(args, d or 0.0, L, W, H, st or "parallel")
            if d is not None:
                if len(atoms) > 1 and closest(atoms) < MIN_DIST:
                    if st == starts[0]:
                        skipped.append(f"d={d:.3f} A: atoms {closest(atoms):.3f} A apart (< {MIN_DIST})")
                    continue
                xs = [pos[0] for _l, pos, _s in atoms]
                if L - (max(xs) - min(xs)) < MIN_GAP:
                    if st == starts[0]:
                        skipped.append(f"d={d:.3f} A: only {L - (max(xs) - min(xs)):.2f} A to the image along x")
                    continue
            case = os.path.join(args.outdir, name) if d is None else \
                os.path.join(args.outdir, name, st, f"d_{d:.3f}A")
            os.makedirs(case, exist_ok=True)
            with open(os.path.join(case, "scf.in"), "w") as fh:
                fh.write(deck(args, atoms, L, W, H, pseudo_abs))
            written += 1

    print(f"{name}: wrote {written} case(s) under {os.path.join(args.outdir, name)}/"
          f"  (box {L:g} x {W:g} x {H:g} A, ecut {args.ecut:g} Ry, pseudos {pseudo_abs})")
    if seps[0] is not None:
        print(f"  separations {seps[0]:.3f} .. {seps[-1]:.3f} A, {len(seps)} on the grid; "
              f"spin starts: {', '.join(starts)}")
    for s in skipped:
        print("  SKIPPED", s)


if __name__ == "__main__":
    main()
