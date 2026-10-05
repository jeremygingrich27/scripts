#!/usr/bin/env python3
"""gen_ecut_relax.py — create one vc-relax subdirectory per plane-wave cutoff.

Like gen_ecut.py, but each
    <outdir>/ecut_<E>Ry/scf.in
is a vc-relax input (calculation='vc-relax', &IONS + &CELL added). At run time
these are meant to be iterated to self-consistency (see update_structure.py);
this script only writes the starting inputs.

    python3 gen_ecut_relax.py --input scf.in --ecuts "60 70 80 90" --cell-dofree all
"""

import argparse
import os

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def generate(input_file, ecuts, outdir, pseudos, cell_dofree, press):
    text = qi.set_pseudo_dir(qi.read_input(input_file), os.path.abspath(pseudos))
    text = qi.make_relax(text, "vc-relax", cell_dofree, press)
    cases = []
    for ecut in ecuts:
        text_e = qi.set_key(text, "system", "ecutwfc", f"{ecut:g}")
        cases.append(qi.write_case(outdir, f"ecut_{ecut:g}Ry", text_e))
    return cases


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="scf.in", help="template pw.x input")
    p.add_argument("--ecuts", required=True,
                   help='ecutwfc values in Ry, e.g. "60 70 80 90 100"')
    p.add_argument("--outdir", default="ecut_relax_sweep",
                   help="parent directory for the ecut_<E>Ry/ cases")
    p.add_argument("--pseudos", default="pseudos",
                   help="directory of .upf files (absolute path written into "
                        "each scf.in)")
    p.add_argument("--cell-dofree", default="all",
                   help="vc-relax cell_dofree: all, ibrav, shape, volume, ...")
    p.add_argument("--press", type=float, default=None,
                   help="target pressure in kbar (omit for QE default)")
    args = p.parse_args(argv)

    ecuts = [float(x) for x in args.ecuts.split()]
    cases = generate(args.input, ecuts, args.outdir, args.pseudos,
                     args.cell_dofree, args.press)
    print(f"created {len(cases)} vc-relax ecut cases in {args.outdir}/:")
    for c in cases:
        print(f"  {c}")


if __name__ == "__main__":
    main()
