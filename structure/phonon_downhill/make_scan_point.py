#!/usr/bin/env python3
"""Write POSCAR(u) = start POSCAR + u * pattern.

pattern.npy is Cartesian, N x 3, scaled so the largest single-atom displacement
is 1 A; so u is the largest single-atom displacement in A.

usage: make_scan_point.py START_POSCAR PATTERN.npy U OUT_POSCAR
"""
import sys
import numpy as np
from dh_lib import read_poscar, write_poscar

start, pattern, u, out = sys.argv[1], np.load(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
s = read_poscar(start)
s["frac"] = s["frac"] + u * pattern @ np.linalg.inv(s["lattice"])
write_poscar(out, s, title="scan point u = %.4f A (largest atom displacement)" % u)
