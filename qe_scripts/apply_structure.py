#!/usr/bin/env python3
"""apply_structure.py — copy the cell + atomic positions from one pw.x input
into another, leaving everything else (namelists, ecut, k-mesh, ...) untouched.

Glue for the final workflow: after the tight vc-relax converges, its relaxed
geometry lives in relax.in (update_structure.py writes it back). This copies that
geometry into scf.in so the phonon scf runs at the relaxed structure:

    python3 apply_structure.py final/relax.in final/scf.in

Both files must be ibrav=0 with explicit CELL_PARAMETERS and ATOMIC_POSITIONS
(the toolkit convention); the destination's cards are rewritten in place.
"""

import argparse
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src", help="input to copy the structure FROM (e.g. relax.in)")
    p.add_argument("dst", help="input to copy the structure INTO (e.g. scf.in)")
    args = p.parse_args(argv)

    src = qi.read_input(args.src)
    cell = qi.get_cell(src)
    _, atoms = qi.get_positions(src)

    dst = qi.read_input(args.dst)
    dst = qi.set_cell(dst, cell)
    dst = qi.set_positions(dst, atoms)
    with open(args.dst, "w") as fh:
        fh.write(dst)
    print(f"  [apply] copied structure {args.src} -> {args.dst}")


if __name__ == "__main__":
    sys.exit(main())
