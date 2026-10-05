#!/usr/bin/env python3
"""gen_kpoints_relax.py — create one vc-relax subdirectory per k-point mesh.

Like gen_kpoints.py, but each
    <outdir>/mesh_<A>x<B>x<C>/scf.in
is a vc-relax input (calculation='vc-relax', &IONS + &CELL added). Meant to be
iterated to self-consistency at run time (see update_structure.py); this script
only writes the starting inputs.

Mesh for sweep size N is set by --kratio (same rules as gen_kpoints.py):
  "1 1 1" (cubic), "auto" (~1/|a_i| from the cell), or "fx fy fz".

    python3 gen_kpoints_relax.py --input scf.in --kn "2 4 6" --kratio auto

--kz K (slabs; amendment signed off 2026-10-05): the mesh is N x M x K, with N, M
from --kn and --kratio applied to a1, a2 only (the vacuum axis is ignored).
    python3 gen_kpoints_relax.py --kn "6 9 12" --kratio auto --kz 1 --cell-dofree 2Dxy
"""

import argparse
import os

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from .gen_kpoints import mesh_from_n
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    from gen_kpoints import mesh_from_n


def generate(input_file, kns, kratio, outdir, pseudos, cell_dofree, press, kz=None):
    text = qi.set_pseudo_dir(qi.read_input(input_file), os.path.abspath(pseudos))
    text = qi.make_relax(text, "vc-relax", cell_dofree, press)
    cell = qi.get_cell(text)            # also enforces ibrav=0 + explicit cell
    cases = []
    for n in kns:
        mesh = mesh_from_n(n, kratio, cell, kz)
        tag = "{}x{}x{}".format(*mesh)
        text_k = qi.set_kpoints(text, mesh)
        cases.append((qi.write_case(outdir, f"mesh_{tag}", text_k), n, mesh))
    return cases


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="scf.in", help="template pw.x input")
    p.add_argument("--kn", required=True,
                   help='sweep sizes for the longest axis, e.g. "2 4 6 8"')
    p.add_argument("--kratio", default="1 1 1",
                   help='"1 1 1" (cubic), "auto", or three numbers')
    p.add_argument("--outdir", default="kpt_relax_sweep",
                   help="parent directory for the mesh_<A>x<B>x<C>/ cases")
    p.add_argument("--pseudos", default="pseudos",
                   help="directory of .upf files (absolute path written into "
                        "each scf.in)")
    p.add_argument("--cell-dofree", default="all",
                   help="vc-relax cell_dofree: all, ibrav, shape, volume, ...")
    p.add_argument("--press", type=float, default=None,
                   help="target pressure in kbar (omit for QE default)")
    p.add_argument("--kz", type=int, default=None,
                   help="slabs: hold the third mesh entry at KZ; --kn and --kratio "
                        "then apply to a1, a2 only")
    args = p.parse_args(argv)

    kns = [int(x) for x in args.kn.split()]
    cases = generate(args.input, kns, args.kratio, args.outdir, args.pseudos,
                     args.cell_dofree, args.press, args.kz)
    print(f"created {len(cases)} vc-relax k-mesh cases in {args.outdir}/:")
    for path, n, mesh in cases:
        print("  N={:<3} -> {:<10} {}".format(n, "{}x{}x{}".format(*mesh), path))


if __name__ == "__main__":
    main()
