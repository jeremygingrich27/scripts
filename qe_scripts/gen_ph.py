#!/usr/bin/env python3
"""gen_ph.py — write the phonon-dispersion inputs (ph.x -> q2r.x -> matdyn.x).

Writes into <outdir>/ (the same dir as the final scf, so they share the scf save
via ESPRESSO_TMPDIR):

  ph.in     : DFPT phonons on a coarse nq1 x nq2 x nq3 q-grid (ldisp=.true.).
  q2r.in    : Fourier-transform the dynamical matrices to real-space force
              constants (applies the acoustic sum rule).
  matdyn.in : interpolate the force constants onto a high-symmetry band path to
              get the dispersion. The band path is taken verbatim from --kpath
              (one "qx qy qz npts" per line), so this script needs no knowledge
              of the lattice's symmetry — supply the path the way you would a
              phonopy HIGH_SYMMETRY_POINTS file. Without --kpath, matdyn.in is
              skipped (ph.in + q2r.in are still written).

outdir is left to ESPRESSO_TMPDIR for every step (the toolkit's $WORK/$SCRATCH
convention), so the scf, ph.x, q2r.x and matdyn.x all just need the same
ESPRESSO_TMPDIR. --epsil adds the dielectric/Born-charge response (LO-TO
splitting) — turn it on for insulators, leave it off for metals/smeared systems.

    python3 gen_ph.py --nq "4 4 4" --kpath kpath.dat            # metal
    python3 gen_ph.py --nq "4 4 1" --epsil --kpath kpath.dat    # insulator
"""

import argparse
import os


PH = """phonons: DFPT on a {nqx}x{nqy}x{nqz} q-grid
&inputph
  prefix = '{prefix}'
  fildyn = '{fildyn}'
  tr2_ph = {tr2}
  ldisp = .true.
  nq1 = {nqx}
  nq2 = {nqy}
  nq3 = {nqz}
  epsil = {epsil}
/
"""

Q2R = """&input
  fildyn = '{fildyn}'
  flfrc = '{flfrc}'
  zasr = '{asr}'
/
"""

MATDYN_HEAD = """&input
  flfrc = '{flfrc}'
  flfrq = '{flfrq}'
  asr = '{asr}'
  q_in_band_form = .true.
  q_in_cryst_coord = {cryst}
/
"""


def _read_kpath(path):
    """Return the band-path lines (qx qy qz npts), dropping blanks/comments."""
    lines = []
    with open(path) as fh:
        for raw in fh:
            s = raw.split("#", 1)[0].split("!", 1)[0].strip()
            if s:
                lines.append(s)
    if not lines:
        raise SystemExit(f"{path}: no band-path points found")
    return lines


def generate(outdir, prefix, nq, tr2, fildyn, flfrc, flfrq, asr, epsil,
             kpath, kpath_cryst):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "ph.in"), "w") as fh:
        fh.write(PH.format(prefix=prefix, fildyn=fildyn, tr2=tr2,
                           nqx=nq[0], nqy=nq[1], nqz=nq[2],
                           epsil=".true." if epsil else ".false."))
    with open(os.path.join(outdir, "q2r.in"), "w") as fh:
        fh.write(Q2R.format(fildyn=fildyn, flfrc=flfrc, asr=asr))

    wrote = ["ph.in", "q2r.in"]
    if kpath:
        path_lines = _read_kpath(kpath)
        body = MATDYN_HEAD.format(flfrc=flfrc, flfrq=flfrq, asr=asr,
                                  cryst=".true." if kpath_cryst else ".false.")
        body += f"{len(path_lines)}\n" + "\n".join(path_lines) + "\n"
        with open(os.path.join(outdir, "matdyn.in"), "w") as fh:
            fh.write(body)
        wrote.append("matdyn.in")
    return wrote


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--outdir", default="final", help="dir to write the inputs into")
    p.add_argument("--prefix", default="pwscf", help="QE prefix of the scf save")
    p.add_argument("--nq", required=True, help='phonon q-grid "A B C" (ldisp)')
    p.add_argument("--tr2-ph", default="1.0d-14", help="ph.x tr2_ph (default 1.0d-14)")
    p.add_argument("--fildyn", default="ph.dyn", help="dynamical-matrix file base")
    p.add_argument("--flfrc", default="q2r.fc", help="real-space force-constant file")
    p.add_argument("--flfrq", default="matdyn.freq", help="matdyn frequency output")
    p.add_argument("--asr", default="crystal",
                   help="acoustic sum rule for q2r/matdyn: crystal, simple, no")
    p.add_argument("--epsil", action="store_true",
                   help="compute dielectric tensor + Born charges (insulators)")
    p.add_argument("--kpath", default=None,
                   help='band-path file ("qx qy qz npts" per line) for matdyn.in')
    p.add_argument("--kpath-cartesian", action="store_true",
                   help="band path is in 2pi/a cartesian coords (default: crystal)")
    args = p.parse_args(argv)

    nq = [int(x) for x in args.nq.split()]
    wrote = generate(args.outdir, args.prefix, nq, args.tr2_ph, args.fildyn,
                     args.flfrc, args.flfrq, args.asr, args.epsil,
                     args.kpath, not args.kpath_cartesian)
    print(f"wrote {', '.join(wrote)} in {args.outdir}/  "
          f"(q-grid {args.nq}, epsil={'on' if args.epsil else 'off'})")
    if not args.kpath:
        print("  note: no --kpath given, matdyn.in skipped "
              "(supply a band path to get the dispersion)")


if __name__ == "__main__":
    main()
