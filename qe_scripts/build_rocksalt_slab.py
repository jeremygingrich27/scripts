#!/usr/bin/env python3
"""build_rocksalt_slab.py — cut an N-plane slab along z from a reoriented
rocksalt bulk (reorient_rocksalt.py output) and write ONE pw.x input.

Implements the pseudocode signed off 2026-10-05. One slab per call; a shell
loop builds a case tree. Inputs only: no running, no post-processing.

    build_rocksalt_slab.py --bulk BULK_DIR --layers N --pseudos pseudos --out CASE/scf.in \
                           [--bottom Sc|N] [--supercell "n m"] [--vacuum 20] \
                           [--relax-free F] [--dipole auto|on|off] \
                           [--forc-thr 1.0d-5 --etot-thr 1.0d-6] [--kmesh "12 12"]

Planes: bulk cells stacked along c, atoms grouped by z. The slab is N
consecutive planes.
  001: every plane is stoichiometric; the slab starts on the first plane.
  111: planes alternate pure cation / pure anion; --bottom picks the bottom
       species. Odd N: same termination both sides (non-stoichiometric, no net
       dipole). Even N: stoichiometric, opposite terminations (polar).

Cell: a1, a2 from the bulk times the supercell; c = thickness + vacuum; bottom
plane at vacuum/2. --relax-free F > 0 gives calculation='relax' with the outer
F planes of each side free (1 1 1) and the rest fixed (0 0 0); F = 0 gives
calculation='scf'. --dipole auto turns the sawtooth dipole correction
(make_deposition.add_dipole) on only when the slab is not symmetric under
z -> -z (mirror or inversion, up to an in-plane shift).

--forc-thr / --etot-thr (amendment 2026-10-07; defaults 1.0d-5 / 1.0d-6, as
build_slab.py) set forc_conv_thr / etot_conv_thr in relax inputs only.
--kmesh "k1 k2" (amendment 2026-10-07) sets the in-plane mesh directly (kz = 1),
replacing the bulk-mesh / supercell default.

Everything else (ecut, U, smearing, species) is copied from BULK_DIR/scf.in.
pseudo_dir is the absolute path of --pseudos, so build on the machine that runs
the case. K-mesh: bulk in-plane mesh / supercell (rounded up), kz = 1.
"""

import argparse
import math
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import make_deposition as md
    from .build_slab import read_bulk
    from .reorient_rocksalt import get_kmesh
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import make_deposition as md
    from build_slab import read_bulk
    from reorient_rocksalt import get_kmesh

ZTOL = 0.05         # atoms within this many A in z share a plane
TOL = 1e-4          # fractional-coordinate tolerance


def planes(atoms, c, n_needed):
    """Bulk stacked along c, grouped into planes bottom to top:
    [[(el, fx, fy, z_cart), ...], ...] with at least n_needed + a few planes."""
    per_cell = len({round((f[2] % 1.0) * c / ZTOL) for _el, f in atoms})
    reps = n_needed // per_cell + 3
    rows = sorted(((el, f[0] % 1.0, f[1] % 1.0, ((f[2] % 1.0) + r) * c)
                   for r in range(reps) for el, f in atoms), key=lambda t: t[3])
    out = [[rows[0]]]
    for row in rows[1:]:
        if row[3] - out[-1][0][3] < ZTOL:
            out[-1].append(row)
        else:
            out.append([row])
    return out


def _same(a, b):
    """Two lists of (el, fx, fy, z) are the same set, in-plane fractions mod 1."""
    if len(a) != len(b):
        return False
    def d(u, v):
        return abs((u - v + 0.5) % 1.0 - 0.5)
    return all(any(e1 == e2 and d(x1, x2) < TOL and d(y1, y2) < TOL and abs(z1 - z2) < 1e-3
                   for e2, x2, y2, z2 in b) for e1, x1, y1, z1 in a)


def is_symmetric(rows):
    """True if z -> -z, with (x, y) kept (mirror) or negated (inversion), maps
    the slab onto itself up to an in-plane translation."""
    ztop, zbot = max(r[3] for r in rows), min(r[3] for r in rows)
    for sign in (1, -1):
        img = [(el, sign * x, sign * y, ztop + zbot - z) for el, x, y, z in rows]
        ref = rows[0]
        for el, x, y, z in img:                 # try shifts that land on rows[0]
            if el != ref[0] or abs(z - ref[3]) > 1e-3:
                continue
            tx, ty = ref[1] - x, ref[2] - y
            if _same([(e, a + tx, b + ty, zz) for e, a, b, zz in img], rows):
                return True
    return False


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bulk", required=True, help="reoriented bulk dir (reorient_rocksalt.py)")
    p.add_argument("--layers", type=int, required=True, help="number of planes N")
    p.add_argument("--pseudos", required=True, help="dir holding the bulk's .upf files")
    p.add_argument("--out", required=True, help="path of the scf.in to write")
    p.add_argument("--bottom", help="111 only: species of the bottom plane")
    p.add_argument("--supercell", default="1 1", help='in-plane repeat "n m" (default 1 1)')
    p.add_argument("--vacuum", type=float, default=20.0, help="vacuum in A (default 20)")
    p.add_argument("--relax-free", type=int, default=0,
                   help="free planes per side; 0 = unrelaxed scf (default 0)")
    p.add_argument("--dipole", choices=["auto", "on", "off"], default="auto",
                   help="dipole correction (default auto: on if the slab is not symmetric)")
    p.add_argument("--forc-thr", default="1.0d-5", help="relax forc_conv_thr (default 1.0d-5)")
    p.add_argument("--etot-thr", default="1.0d-6", help="relax etot_conv_thr (default 1.0d-6)")
    p.add_argument("--kmesh", help='in-plane mesh "k1 k2" (z gets 1); default: bulk mesh / supercell')

    args = p.parse_args(argv)

    # 1. read the reoriented bulk
    cell, atoms, source = read_bulk(args.bulk)
    template = qi.read_input(os.path.join(args.bulk, "scf.in"))
    a1, a2, a3 = cell
    if abs(a3[0]) > 1e-6 or abs(a3[1]) > 1e-6 or abs(a1[2]) > 1e-6 or abs(a2[2]) > 1e-6:
        sys.exit("bulk a3 is not along z (run reorient_rocksalt.py first)")
    c_bulk = a3[2]
    N, F = args.layers, args.relax_free
    if N < 1:
        sys.exit("--layers must be at least 1")
    if F < 0 or 2 * F > N:
        sys.exit("--relax-free must be between 0 and layers/2")
    n, m = (int(x) for x in args.supercell.split())

    # 2. planes
    stack = planes(atoms, c_bulk, N)
    pure = all(len({r[0] for r in pl}) == 1 for pl in stack)
    mixed = all(len({r[0] for r in pl}) > 1 for pl in stack)
    if not (pure or mixed):
        sys.exit("planes are neither all mixed (001) nor all single-species (111)")

    # 3. pick N consecutive planes
    if pure:
        if not args.bottom:
            sys.exit("polar (111-type) bulk: give --bottom with the bottom-plane species")
        starts = [i for i, pl in enumerate(stack) if pl[0][0] == args.bottom]
        if not starts:
            sys.exit(f"no {args.bottom} plane in the bulk")
        start = starts[0]
    else:
        if args.bottom:
            sys.exit("--bottom is only for polar (111-type) slabs")
        start = 0
    if start + N > len(stack):
        sys.exit("internal: not enough stacked bulk cells")
    chosen = stack[start:start + N]

    # 4. in-plane repeat, plane index k kept for the relax flags
    flat = [(el, (fx + i) / n, (fy + j) / m, z, k)
            for k, pl in enumerate(chosen) for el, fx, fy, z in pl
            for i in range(n) for j in range(m)]

    # 5. cell
    z0 = chosen[0][0][3]
    T = chosen[-1][0][3] - z0
    cs = T + args.vacuum
    base = args.vacuum / 2.0
    rows = [(el, fx, fy, (z - z0 + base) / cs, k) for el, fx, fy, z, k in flat]
    rows.sort(key=lambda r: (r[3], r[0], r[2], r[1]))
    new_cell = [[x * n for x in a1], [x * m for x in a2], [0.0, 0.0, cs]]

    # 7. symmetry and dipole
    sym = is_symmetric([(el, fx, fy, z * cs) for el, fx, fy, z, _k in rows])
    dipole = (args.dipole == "on") or (args.dipole == "auto" and not sym)

    # 8. write
    pseudos = os.path.abspath(args.pseudos)
    species = sorted({r[0] for r in rows})
    for upf in (u for _l, _m, u in md.get_species(template)):
        if not os.path.isfile(os.path.join(pseudos, upf)):
            sys.exit(f"{upf} not found in {pseudos}")
    relax = F > 0
    flags = (lambda k: ["1", "1", "1"] if (k < F or k >= N - F) else ["0", "0", "0"]) \
        if relax else (lambda k: [])
    text = qi.set_key(template, "system", "nat", str(len(rows)))
    text = qi.set_pseudo_dir(text, pseudos)
    text = md.set_atoms(text, [(el, [fx, fy, fz], flags(k)) for el, fx, fy, fz, k in rows])
    text = qi.set_cell(text, new_cell)
    if args.kmesh:
        if len(args.kmesh.split()) != 2:
            sys.exit('--kmesh takes two numbers, e.g. "12 12"')
        k_new = [int(k) for k in args.kmesh.split()] + [1]
    else:
        k_bulk = get_kmesh(template)
        k_new = [math.ceil(k_bulk[0] / n), math.ceil(k_bulk[1] / m), 1]
    text = qi.set_kpoints(text, k_new)
    if relax:
        text = qi.make_relax(text, calculation="relax")
        text = qi.set_key(text, "control", "forc_conv_thr", args.forc_thr)
        text = qi.set_key(text, "control", "etot_conv_thr", args.etot_thr)
    else:
        text = qi.set_key(text, "control", "calculation", "'scf'")
    if dipole:
        text = md.add_dipole(text, rows[0][3], rows[-1][3])

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(text)

    # 9. report
    counts = {s: sum(1 for r in rows if r[0] == s) for s in species}
    stoich = len(set(counts.values())) == 1
    print(f"{args.out}: {N} planes ({len(rows)} atoms), supercell {n}x{m}, "
          f"{'relax' if relax else 'scf'}")
    print(f"  bulk from {source}; k-mesh {k_new[0]} {k_new[1]} 1")
    print(f"  slab T = {T:.3f} A, cell c = {cs:.3f} A, vacuum {args.vacuum:g} A")
    print(f"  composition {' '.join(f'{s}{c}' for s, c in counts.items())} "
          f"({'stoichiometric' if stoich else 'non-stoichiometric'}), "
          f"{'symmetric' if sym else 'NOT symmetric'}, dipole {'on' if dipole else 'off'}")
    for k, pl in enumerate(chosen):
        z = base + pl[0][3] - z0
        els = [r[0] for r in pl]
        tag = " free" if relax and (k < F or k >= N - F) else (" fixed" if relax else "")
        print(f"  plane {k:2d}  z = {z:8.3f} A  "
              + " ".join(f"{s}x{els.count(s) * n * m}" for s in species if s in els) + tag)
    if relax:
        nfree = sum(1 for r in rows if r[4] < F or r[4] >= N - F)
        print(f"  free atoms {nfree}, fixed {len(rows) - nfree}")


if __name__ == "__main__":
    main()
