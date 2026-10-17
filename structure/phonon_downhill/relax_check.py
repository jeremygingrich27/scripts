#!/usr/bin/env python3
"""Judge one finished relaxation round.

Prints ONE action as its last line:
  CONVERGED      VASP reached the required accuracy within its FIRST ionic step
                 (so the cell no longer moves: Pulay stress gone)
  CONTINUE       run another round from this CONTCAR
  HALT <reason>  a or b moved (the clamp failed) or the run did not finish

The AFII moment check is check_moments.py; the job runs both.

usage: relax_check.py ROUND_DIR CLAMP_POSCAR AB_TOL_ANGSTROM
"""
import sys
import numpy as np
from dh_lib import read_poscar, finished

run, ref, tol = sys.argv[1], sys.argv[2], float(sys.argv[3])

if not finished(run + "/OUTCAR"):
    print("HALT run did not finish (no timing block in OUTCAR)")
    sys.exit()

# the clamp: a and b must be exactly the start cell's (LATTICE_CONSTRAINTS = F F T)
a0, a1 = read_poscar(ref)["lattice"], read_poscar(run + "/CONTCAR")["lattice"]
moved = np.abs(a1[:2] - a0[:2]).max()
print("a,b change vs clamp cell: %.2e A; c: %.5f -> %.5f A" % (
    moved, np.linalg.norm(a0[2]), np.linalg.norm(a1[2])))
if moved > tol:
    print("HALT a or b moved by %.2e A (LATTICE_CONSTRAINTS did not hold)" % moved)
    sys.exit()

ionic_steps = sum(1 for line in open(run + "/OSZICAR") if " F= " in line)
reached = "reached required accuracy" in open(run + "/OUTCAR").read()
print("ionic steps %d, required accuracy %s" % (ionic_steps, "reached" if reached else "NOT reached"))
print("CONVERGED" if reached and ionic_steps == 1 else "CONTINUE")
