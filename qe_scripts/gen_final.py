#!/usr/bin/env python3
"""gen_final.py — write the final production directory: a tight vc-relax plus the
scf that feeds a phonon (ph.x) run.

Seeds from a template that already holds a good (relaxed) structure — typically
the converged case picked out of a sweep (see pick_converged.py) — and writes
into <outdir>/:

  relax.in : vc-relax at the chosen ecut + k-mesh, with *tight* thresholds
             (conv_thr, forc_conv_thr, etot_conv_thr) so residual stress/forces
             don't leak into the phonons. Meant to be iterated to
             self-consistency at run time (update_structure.py), exactly like the
             sweep relaxes.
  scf.in   : a plain scf at the same ecut + k-mesh, used to generate the
             wavefunctions ph.x reads. Its structure is a placeholder — the
             jobscript copies the relaxed geometry from relax.in into it
             (apply_structure.py) once the relax has converged.

Both files set an explicit `prefix` so the scf save and ph.x agree on it; outdir
is left to ESPRESSO_TMPDIR (the toolkit's $WORK/$SCRATCH convention), so scf and
ph.x just need to run with the same ESPRESSO_TMPDIR.

Occupations default to 'fixed' rather than inheriting the seed's: the sweeps use
smearing for robustness, but smearing makes ph.x treat the system as a metal and
refuse epsil/Born-charge calculations. Pass --occupations smearing for a genuine
metal, or --occupations inherit to keep the seed's scheme.

    python3 gen_final.py --input converged/scf.in --ecut 90 --mesh "10 10 2"
"""

import argparse
import os

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def generate(input_file, ecut, mesh, outdir, pseudos, prefix,
             cell_dofree, press, conv_thr, forc_thr, etot_thr,
             occupations, smearing, degauss):
    base = qi.set_pseudo_dir(qi.read_input(input_file), os.path.abspath(pseudos))
    qi.get_cell(base)                       # enforce ibrav=0 + explicit cell
    base = qi.set_ecut(base, ecut)
    base = qi.set_kpoints(base, mesh)
    base = qi.set_key(base, "control", "prefix", f"'{prefix}'")
    if occupations != "inherit":            # production runs feed insulator
        base = qi.set_occupations(base, occupations, smearing, degauss)

    relax = qi.make_relax(base, "vc-relax", cell_dofree, press)
    relax = qi.set_key(relax, "control", "forc_conv_thr", forc_thr)
    relax = qi.set_key(relax, "control", "etot_conv_thr", etot_thr)
    relax = qi.set_key(relax, "electrons", "conv_thr", conv_thr)

    scf = qi.set_key(base, "control", "calculation", "'scf'")
    scf = qi.set_key(scf, "electrons", "conv_thr", conv_thr)

    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "relax.in"), "w") as fh:
        fh.write(relax)
    with open(os.path.join(outdir, "scf.in"), "w") as fh:
        fh.write(scf)
    return outdir


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="scf.in",
                   help="seed input holding the (relaxed) structure to start from")
    p.add_argument("--ecut", required=True, help="ecutwfc in Ry (from the sweep)")
    p.add_argument("--mesh", required=True, help='k-mesh "A B C" (from the sweep)')
    p.add_argument("--outdir", default="final", help="output directory")
    p.add_argument("--pseudos", default="pseudos",
                   help="dir of .upf files (absolute path written into the inputs)")
    p.add_argument("--prefix", default="pwscf",
                   help="QE prefix shared by the scf save and ph.x (default pwscf)")
    p.add_argument("--cell-dofree", default="all",
                   help="vc-relax cell_dofree: all, ibrav, shape, volume, ...")
    p.add_argument("--press", type=float, default=None,
                   help="target pressure in kbar (omit for QE default)")
    p.add_argument("--conv-thr", default="1.0d-10",
                   help="electronic conv_thr for relax and scf (default 1.0d-10)")
    p.add_argument("--forc-thr", default="1.0d-5",
                   help="vc-relax forc_conv_thr in Ry/bohr (default 1.0d-5)")
    p.add_argument("--etot-thr", default="1.0d-6",
                   help="vc-relax etot_conv_thr in Ry (default 1.0d-6)")
    p.add_argument("--occupations", choices=["fixed", "smearing", "inherit"],
                   default="fixed",
                   help="occupation scheme for relax+scf. Default 'fixed': these "
                        "feed phonons of an insulator, and smearing makes ph.x "
                        "treat the system as a metal (epsil/Born charges fail). "
                        "Use 'smearing' for a metal, 'inherit' to keep the seed's.")
    p.add_argument("--smearing", default="gaussian",
                   help="smearing type when --occupations smearing (default gaussian)")
    p.add_argument("--degauss", type=float, default=0.004,
                   help="degauss in Ry when --occupations smearing (default 0.004)")
    args = p.parse_args(argv)

    mesh = [int(x) for x in args.mesh.split()]
    outdir = generate(args.input, args.ecut, mesh, args.outdir, args.pseudos,
                      args.prefix, args.cell_dofree, args.press,
                      args.conv_thr, args.forc_thr, args.etot_thr,
                      args.occupations, args.smearing, args.degauss)
    print(f"wrote {outdir}/relax.in and {outdir}/scf.in  "
          f"(ecut={args.ecut} Ry, mesh={args.mesh}, prefix={args.prefix}, "
          f"occupations={args.occupations})")


if __name__ == "__main__":
    main()
