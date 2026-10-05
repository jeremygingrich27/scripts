#!/usr/bin/env python3
"""build_slab.py — cut an N-bilayer slab along c from a relaxed bulk of a
hexagonal tetrahedral (bilayer-stacked) crystal and write ONE pw.x input.

Implements the pseudocode signed off 2026-10-03. One slab per call; a shell
loop builds a case tree. Inputs only: no running, no post-processing.

    build_slab.py --bulk BULK_DIR --bilayers 8 --orientation up \
                  --ecut 122 --kmesh "10 10" --pseudos pseudos --out case/scf.in \
                  [--vacuum 20] [--relax-free 2] [--spin 0.5] [--degauss 0.01] \
                  [--conv-thr 1.0e-8] [--mixing-beta 0.4] \
                  [--hubbard "Ga-3d 3.9 ortho-atomic"] [--forc-thr 1.0d-5 --etot-thr 1.0d-6]

Bulk geometry: final cell + crystal positions from BULK_DIR/scf.out (vc-relax),
else BULK_DIR/scf.in. a3 must be along z.

Bilayers: bulk cells are stacked along c and atoms sorted by z. The vertical
gaps must alternate short (inside a bilayer) / long (the single bond along c);
a bilayer is the two atoms across a short gap and must be one cation + one
anion. The slab takes N consecutive bilayers, so it is cut through long gaps
(one broken bond per surface atom). For GaN this leaves Ga on top (+z = [0001]);
for SiC, Si on top. --orientation down mirrors z -> -z (anion face up).

Cell: a1, a2 from the bulk; c = slab thickness + vacuum; bottom plane at
vacuum/2. --relax-free F > 0 gives calculation='relax' with the outer F
bilayers of each side free (1 1 1) and the rest fixed (0 0 0); F = 0 gives
calculation='scf'. --spin S > 0 gives nspin=2 with starting_magnetization = S
on every species, else nspin=1. The dipole correction (sawtooth mid-vacuum) is
make_deposition.add_dipole. pseudo_dir is the absolute path of --pseudos, so
build on the machine that runs the case.

--occupations fixed|smearing (amendment signed off 2026-10-03; default
smearing): fixed writes occupations='fixed' with no smearing keys; smearing
writes gaussian smearing of width --degauss.
"""

import argparse
import math
import os
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import qe_output as qo
    from . import make_deposition as md
    from .gen_pair_curve import MASSES
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import qe_output as qo
    import make_deposition as md
    from gen_pair_curve import MASSES


def read_bulk(bulk_dir):
    """(cell [A], [(element, [fx, fy, fz]), ...], source)."""
    out_path = os.path.join(bulk_dir, "scf.out")
    if os.path.isfile(out_path):
        st = qo.parse_final_structure(open(out_path).read())
        if st is not None:
            return st["cell"], st["atoms"], out_path + " (final coordinates)"
    text = qi.read_input(os.path.join(bulk_dir, "scf.in"))
    lines = text.splitlines()
    _i, unit = qi._find_cell(lines)
    if "angstrom" not in (unit or "").lower():
        sys.exit("bulk CELL_PARAMETERS must be in angstrom")
    unit, rows = md.get_atoms(text)
    if unit != "crystal":
        sys.exit("bulk ATOMIC_POSITIONS must be in crystal units")
    return qi.get_cell(text), [(lab, xyz) for lab, xyz, _f in rows], \
        os.path.join(bulk_dir, "scf.in")


def bilayer_stack(atoms, c, n_bilayers):
    """List of N bilayers, each [(el, fx, fy, z_cart), (el, fx, fy, z_cart)],
    bottom to top, cut through the long gaps."""
    per_cell = len(atoms)
    reps = n_bilayers * 2 // per_cell + 3
    rows = []
    for r in range(reps):
        for el, (fx, fy, fz) in atoms:
            rows.append((el, fx % 1.0, fy % 1.0, ((fz % 1.0) + r) * c))
    rows.sort(key=lambda t: t[3])
    gaps = [rows[i + 1][3] - rows[i][3] for i in range(len(rows) - 1)]
    thr = (min(gaps) + max(gaps)) / 2.0
    short = [g < thr for g in gaps]
    if any(short[i] == short[i + 1] for i in range(len(short) - 1)):
        sys.exit("vertical gaps do not alternate short/long: not a bilayer stacking")
    # first atom that starts a bilayer: the gap above it is short
    start = 0 if short[0] else 1
    need = 2 * n_bilayers
    if start + need > len(rows):
        sys.exit("internal: not enough stacked bulk cells")
    chosen = rows[start:start + need]
    bls = [chosen[2 * k:2 * k + 2] for k in range(n_bilayers)]
    for k, (lo, hi) in enumerate(bls):
        if lo[0] == hi[0]:
            sys.exit(f"bilayer {k} is {lo[0]}-{hi[0]}: not one cation + one anion")
    return bls, max(g for g in gaps if g >= thr), min(gaps)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bulk", required=True, help="bulk dir with scf.out (vc-relax) or scf.in")
    p.add_argument("--bilayers", type=int, required=True, help="number of bilayers N")
    p.add_argument("--orientation", choices=["up", "down"], required=True,
                   help="up: as cut (cation face on top); down: mirrored z (anion face on top)")
    p.add_argument("--ecut", type=float, required=True, help="ecutwfc in Ry")
    p.add_argument("--kmesh", required=True, help='in-plane mesh "k1 k2" (z gets 1)')
    p.add_argument("--pseudos", required=True, help="dir holding <El>.upf")
    p.add_argument("--out", required=True, help="path of the scf.in to write")
    p.add_argument("--vacuum", type=float, default=20.0, help="vacuum in A (default 20)")
    p.add_argument("--relax-free", type=int, default=0,
                   help="free bilayers per side; 0 = unrelaxed scf (default 0)")
    p.add_argument("--spin", type=float, default=0.0,
                   help="starting_magnetization on every species; >0 turns on nspin=2")
    p.add_argument("--occupations", choices=["fixed", "smearing"], default="smearing",
                   help="occupation scheme (default smearing)")
    p.add_argument("--degauss", type=float, default=0.01,
                   help="gaussian smearing in Ry, with --occupations smearing (default 0.01)")
    p.add_argument("--conv-thr", default="1.0e-8", help="conv_thr (default 1.0e-8)")
    p.add_argument("--mixing-beta", default="0.4", help="mixing_beta (default 0.4)")
    p.add_argument("--hubbard", help='e.g. "Ga-3d 3.9 ortho-atomic" (added if that element is present)')
    p.add_argument("--forc-thr", default="1.0d-5", help="relax forc_conv_thr (default 1.0d-5)")
    p.add_argument("--etot-thr", default="1.0d-6", help="relax etot_conv_thr (default 1.0d-6)")
    args = p.parse_args(argv)

    cell, atoms, source = read_bulk(args.bulk)
    a1, a2, a3 = cell
    if abs(a3[0]) > 1e-6 or abs(a3[1]) > 1e-6:
        sys.exit("bulk a3 is not along z")
    c_bulk = a3[2]
    N, F = args.bilayers, args.relax_free
    if F < 0 or 2 * F > N:
        sys.exit("--relax-free must be between 0 and bilayers/2")

    bls, long_gap, short_gap = bilayer_stack(atoms, c_bulk, N)
    flat = [(el, fx, fy, z, k) for k, bl in enumerate(bls) for el, fx, fy, z in bl]
    if args.orientation == "down":                     # mirror z, renumber bilayers
        ztop = flat[-1][3]
        flat = [(el, fx, fy, ztop - z, N - 1 - k) for el, fx, fy, z, k in flat]
        flat.sort(key=lambda t: t[3])
    z0 = flat[0][3]
    T = flat[-1][3] - z0
    cs = T + args.vacuum
    base = args.vacuum / 2.0
    rows = [(el, fx, fy, (z - z0 + base) / cs, k) for el, fx, fy, z, k in flat]
    zlo, zhi = rows[0][3], rows[-1][3]

    species = sorted({r[0] for r in rows})
    for el in species:
        if el not in MASSES:
            sys.exit(f"no mass for {el}: add it to MASSES in gen_pair_curve.py")
        if not os.path.isfile(os.path.join(os.path.abspath(args.pseudos), f"{el}.upf")):
            sys.exit(f"{el}.upf not found in {os.path.abspath(args.pseudos)}")
    relax = F > 0
    k1, k2 = args.kmesh.split()

    L = ["&CONTROL", f"  calculation = '{'relax' if relax else 'scf'}'", "  prefix = 'slab'",
         f"  pseudo_dir = '{os.path.abspath(args.pseudos)}'", "  verbosity = 'high'",
         "  disk_io = 'low'"]
    if relax:
        L += [f"  forc_conv_thr = {args.forc_thr}", f"  etot_conv_thr = {args.etot_thr}"]
    L += ["/", "&SYSTEM", "  ibrav = 0", f"  nat = {len(rows)}", f"  ntyp = {len(species)}",
          f"  ecutwfc = {args.ecut:g}", f"  nspin = {2 if args.spin > 0 else 1}"]
    if args.spin > 0:
        L += [f"  starting_magnetization({i + 1}) = {args.spin}" for i in range(len(species))]
    if args.occupations == "fixed":
        L.append("  occupations = 'fixed'")
    else:
        L += ["  occupations = 'smearing'", "  smearing = 'gaussian'", f"  degauss = {args.degauss}"]
    L += ["/", "&ELECTRONS", f"  conv_thr = {args.conv_thr}", f"  mixing_beta = {args.mixing_beta}", "/"]
    if relax:
        L += ["&IONS", "/"]
    L += ["ATOMIC_SPECIES"] + [f"  {el:<3} {MASSES[el]}  {el}.upf" for el in species]
    L.append("ATOMIC_POSITIONS (crystal)")
    for el, fx, fy, fz, k in rows:
        flag = ("  1 1 1" if (k < F or k >= N - F) else "  0 0 0") if relax else ""
        L.append(f"  {el:<3} {fx:.10f}  {fy:.10f}  {fz:.10f}{flag}")
    L += ["CELL_PARAMETERS (angstrom)",
          f"  {a1[0]:.10f}  {a1[1]:.10f}  {a1[2]:.10f}",
          f"  {a2[0]:.10f}  {a2[1]:.10f}  {a2[2]:.10f}",
          f"  0.0000000000  0.0000000000  {cs:.10f}",
          "K_POINTS automatic", f"  {k1} {k2} 1 0 0 0"]
    if args.hubbard:
        label, value, proj = args.hubbard.split()
        if label.split("-")[0] in species:
            L += [f"HUBBARD ({proj})", f"U {label} {value}"]
    text = md.add_dipole("\n".join(L) + "\n", zlo, zhi)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(text)

    nfree = sum(1 for r in rows if relax and (r[4] < F or r[4] >= N - F))
    print(f"{args.out}: {N} bilayers ({len(rows)} atoms), orientation {args.orientation}, "
          f"{'relax' if relax else 'scf'}, nspin {2 if args.spin > 0 else 1}")
    print(f"  bulk from {source}: a = {math.hypot(a1[0], a1[1]):.5f} A, c = {c_bulk:.5f} A; "
          f"gaps short {short_gap:.3f} / long {long_gap:.3f} A")
    print(f"  slab T = {T:.3f} A, cell c = {cs:.3f} A; bottom {rows[0][0]} z = {base:.3f} A, "
          f"top {rows[-1][0]} z = {base + T:.3f} A")
    if relax:
        print(f"  free atoms {nfree}, fixed {len(rows) - nfree}")


if __name__ == "__main__":
    main()
