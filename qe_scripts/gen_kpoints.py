#!/usr/bin/env python3
"""gen_kpoints.py — create one subdirectory per k-point mesh.

Reads a pw.x template, then for each sweep size N builds an automatic mesh and
writes
    <outdir>/mesh_<A>x<B>x<C>/scf.in
with pseudo_dir pinned to the absolute path of --pseudos. Generates inputs
only; it does not run pw.x.

The mesh for size N is set by --kratio:
  "1 1 1"  (default) -> cubic  N N N
  "auto"             -> per-axis factors ~ 1/|a_i| from CELL_PARAMETERS, with
                        N labelling the longest axis (denser along short axes)
  "fx fy fz"         -> explicit per-axis factors

    python3 gen_kpoints.py --input scf.in --kn "2 4 6 8" --kratio auto
"""

import argparse
import math
import os

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def _vlen(v):
    return math.sqrt(sum(c * c for c in v))


def mesh_from_n(n, kratio, cell, kz=None):
    """Turn sweep size `n` into a 3-element mesh using `kratio` and `cell`.
    With `kz` (slabs), the ratio uses a1, a2 only and the third entry is `kz`."""
    if kz is not None:
        if kratio == "auto":
            lengths = [_vlen(v) for v in cell[:2]]
            factors = [max(lengths) / li for li in lengths]
        else:
            factors = [float(x) for x in kratio.split()][:2]
            if len(factors) != 2:
                raise ValueError('--kratio must be "auto" or three numbers')
        fmin = min(factors)
        return [max(1, round(n * f / fmin)) for f in factors] + [kz]
    if kratio == "auto":
        lengths = [_vlen(v) for v in cell]
        factors = [max(lengths) / li for li in lengths]   # ~ 1/|a_i|
    else:
        factors = [float(x) for x in kratio.split()]
        if len(factors) != 3:
            raise ValueError('--kratio must be "auto" or three numbers')
    fmin = min(factors)
    factors = [f / fmin for f in factors]                 # smallest -> 1
    return [max(1, round(n * f)) for f in factors]


def generate(input_file, kns, kratio, outdir, pseudos):
    text = qi.set_pseudo_dir(qi.read_input(input_file), os.path.abspath(pseudos))
    cell = qi.get_cell(text)            # also enforces ibrav=0 + explicit cell
    cases = []
    for n in kns:
        mesh = mesh_from_n(n, kratio, cell)
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
    p.add_argument("--outdir", default="kpt_sweep",
                   help="parent directory for the mesh_<A>x<B>x<C>/ cases")
    p.add_argument("--pseudos", default="pseudos",
                   help="directory of .upf files (its absolute path is "
                        "written into each scf.in)")
    args = p.parse_args(argv)

    kns = [int(x) for x in args.kn.split()]
    cases = generate(args.input, kns, args.kratio, args.outdir, args.pseudos)
    print(f"created {len(cases)} k-mesh cases in {args.outdir}/:")
    for path, n, mesh in cases:
        print("  N={:<3} -> {:<10} {}".format(n, "{}x{}x{}".format(*mesh), path))


if __name__ == "__main__":
    main()
