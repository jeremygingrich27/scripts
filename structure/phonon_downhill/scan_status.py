#!/usr/bin/env python3
"""What should a downhill scan do next?

Reads the finished points u_<u>/ (and check_u_<u>/) in SCAN_DIR, writes scan.dat,
and prints ONE action as its last line:

  NEXT <u>        run the next grid point
  CHECK <u>       minimum bracketed; run the check point at the fitted u
  MIN <dir>       done; <dir> holds the structure at the minimum
  NOMIN           the lowest point is u = 0: not downhill along this direction
  HALT <reason>   moments lost before a minimum was bracketed

Rules (decided 2026-10-16): fixed STEP; bracketed when NPAST points lie past the
lowest; quartic fit to the lowest point + 2 neighbours each side; the check point
must be lower than both grid points around it, otherwise the lowest grid point
is used.  A point holding MOMENTS_LOST ends the scan at the point before it.

usage: scan_status.py SCAN_DIR STEP NPAST
"""
import glob
import os
import sys
import numpy as np
from dh_lib import final_energy

scan, step, npast = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])


def done(p):
    return os.path.exists(p + "/COMPLETED")


# grid points that finished, in order of u
pts = sorted((float(p.split("u_")[-1]), p) for p in glob.glob(scan + "/u_*") if done(p))
lost = [p for u, p in pts if os.path.exists(p + "/MOMENTS_LOST")]
if lost:
    first_bad = min(u for u, p in pts if p in lost)
    pts = [(u, p) for u, p in pts if u < first_bad]
u = np.array([x[0] for x in pts])
e = np.array([final_energy(p + "/OUTCAR") for _, p in pts])
np.savetxt(scan + "/scan.dat", np.column_stack([u, e, (e - e[0]) * 1000 if len(e) else e]),
           fmt="%.4f %.8f %.3f", header="u(A)  E(eV)  E-E(0) (meV)")

if len(u) == 0:
    print("NEXT %.3f" % 0.0)
    sys.exit()
i = int(np.argmin(e))
bracketed = len(u) - 1 - i >= npast

if not bracketed:
    print("HALT moments lost at u = %.3f before a minimum was bracketed" % first_bad if lost
          else "NEXT %.3f" % (u[-1] + step))
    sys.exit()
if i == 0:
    print("NOMIN")
    sys.exit()

# quartic through the lowest point and two neighbours each side
lo, hi = max(0, i - 2), min(len(u), i + 3)
c = np.polyfit(u[lo:hi], e[lo:hi], 4)
grid = np.linspace(u[i - 1], u[i + 1], 2001)
u_fit = grid[np.argmin(np.polyval(c, grid))]

check = "%s/check_u_%.4f" % (scan, u_fit)
if not done(check):
    print("CHECK %.4f" % u_fit)
    sys.exit()

# check point must beat both grid points around it
e_check = final_energy(check + "/OUTCAR")
left, right = u[u <= u_fit].max(), u[u >= u_fit].min()
neighbours = [e[u == left][0], e[u == right][0]]
good = not os.path.exists(check + "/MOMENTS_LOST") and e_check < min(neighbours)
print("fit u = %.4f, check E = %.6f, grid neighbours %s -> %s" % (
    u_fit, e_check, np.round(neighbours, 6), "check point" if good else "lowest grid point"))
print("MIN %s" % (check if good else pts[i][1]))
