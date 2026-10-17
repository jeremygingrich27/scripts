#!/usr/bin/env python3
"""Did a VASP run keep the AFII order?

Compares the sign of each Cu d moment (last LDAUPRINT occupation matrices,
tr up - tr down) with the sign of its MAGMOM.  Exit 0 = all signs kept and no
moment below MIN_MOMENT; exit 1 = lost (reason printed).

usage: check_moments.py RUN_DIR [MIN_MOMENT]     (default MIN_MOMENT 0.3 uB)
"""
import sys
import numpy as np
from dh_lib import magmom, onsite_moments

run = sys.argv[1]
min_moment = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3

start = np.array(magmom(run + "/INCAR"))
n_mag = int(np.count_nonzero(start))              # the magnetic (Cu) atoms come first
m = onsite_moments(run + "/OUTCAR", n_mag)

kept = np.sign(m) == np.sign(start[:n_mag])
print("%s: %d/%d signs kept, |m| %.3f-%.3f uB" % (run, kept.sum(), n_mag, abs(m).min(), abs(m).max()))

if not kept.all():
    print("LOST: sign flipped on atoms", list(np.where(~kept)[0] + 1))
    sys.exit(1)
if abs(m).min() < min_moment:
    print("LOST: moment collapsed below %.2f uB" % min_moment)
    sys.exit(1)
