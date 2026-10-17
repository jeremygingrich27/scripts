#!/usr/bin/env python3
"""findsym on a relaxed structure, with the magnetic moments -> .cif record.

Moments are given along c (decided 2026-10-16): MAGMOM m -> (0, 0, m) Cartesian.
The .cif is a record of the symmetry; the phonons use the CONTCAR as is
(decided 2026-10-16; the relax ran with ISYM = 2, so it is already symmetric).

Writes OUTDIR/findsym.in, findsym.out, findsym.cif (as findsym names it), GROUP
(the space-group line findsym reports), DONE.  Exit 1 if findsym fails.

usage: symmetry_step.py CONTCAR MAGMOM_FILE OUTDIR TOLERANCE
"""
import os
import subprocess
import sys
import numpy as np
from dh_lib import read_poscar, symbols

contcar, magfile, out, tol = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
s = read_poscar(contcar)
mag = [float(x) for x in open(magfile).read().split("=")[1].split()]
os.makedirs(out, exist_ok=True)

# moment (0,0,m) Cartesian, in components along UNIT vectors parallel to a, b, c (ISOTROPY convention)
unit = s["lattice"] / np.linalg.norm(s["lattice"], axis=1)[:, None]
inv = np.linalg.inv(unit)
lines = ["!useKeyWords", "!title", "phonon_downhill " + os.path.abspath(contcar),
         "!latticeTolerance", tol, "!atomicPositionTolerance", tol,
         "!latticeBasisVectors"] + ["%.10f %.10f %.10f" % tuple(v) for v in s["lattice"]] + \
        ["!unitCellCentering", "P", "!atomCount", str(len(s["frac"])),
         "!atomType", " ".join(symbols(s)),
         "!atomPosition"] + ["%.10f %.10f %.10f" % tuple(p) for p in s["frac"]] + \
        ["!atomMagneticMoment"] + ["%.6f %.6f %.6f" % tuple(np.array([0, 0, m]) @ inv) for m in mag]
open(out + "/findsym.in", "w").write("\n".join(lines) + "\n")

# findsym seeks within its input, so it must get a real file name (not stdin)
with open(out + "/findsym.out", "w") as fout:
    rc = subprocess.run(["findsym", "findsym.in"], stdout=fout, stderr=subprocess.STDOUT, cwd=out).returncode
text = open(out + "/findsym.out").read()
group = [l.strip() for l in text.splitlines() if "Space Group" in l or "Magnetic Space Group" in l]
if rc != 0 or not group:
    print("findsym failed: see", out + "/findsym.out")
    sys.exit(1)
open(out + "/GROUP", "w").write("\n".join(group) + "\n")
open(out + "/DONE", "w").write("")
print("\n".join(group))
