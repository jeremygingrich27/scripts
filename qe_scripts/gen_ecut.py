#!/usr/bin/env python3
"""gen_ecut.py — create one subdirectory per plane-wave cutoff.

Reads a pw.x template, then for each ecutwfc value writes
    <outdir>/ecut_<E>Ry/scf.in
with that ecutwfc set and pseudo_dir pinned to the absolute path of --pseudos.
Generates inputs only; it does not run pw.x.

    python3 gen_ecut.py --input scf.in --ecuts "60 70 80 90 100"
"""

import argparse
import os

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def generate(input_file, ecuts, outdir, pseudos):
    text = qi.set_pseudo_dir(qi.read_input(input_file), os.path.abspath(pseudos))
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
    p.add_argument("--outdir", default="ecut_sweep",
                   help="parent directory for the ecut_<E>Ry/ cases")
    p.add_argument("--pseudos", default="pseudos",
                   help="directory of .upf files (its absolute path is "
                        "written into each scf.in)")
    args = p.parse_args(argv)

    ecuts = [float(x) for x in args.ecuts.split()]
    cases = generate(args.input, ecuts, args.outdir, args.pseudos)
    print(f"created {len(cases)} ecut cases in {args.outdir}/:")
    for c in cases:
        print(f"  {c}")


if __name__ == "__main__":
    main()
