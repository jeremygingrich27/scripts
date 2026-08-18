#!/usr/bin/env python3
"""
check_scaling.py  –  Validate lattice scaling of POSCAR_scaled_* files.

• Expects an original POSCAR in the current directory.
• Verifies each POSCAR_scaled_* file (flat, not inside subdirs).
• Prints a report and exits with code 0 if all match, 1 otherwise.
"""
import os
import re
import sys
import numpy as np

TOL = 1e-3  # Å tolerance for each lattice vector length

pat = re.compile(r"POSCAR_scaled_([\d\.]+)_([\d\.]+)_([\d\.]+)$")

def read_lattice(path):
    """Return 3×3 lattice vectors (Å) accounting for global scale factor."""
    with open(path) as f:
        lines = f.readlines()
    scale = float(lines[1].strip())
    lattice = np.array([[float(x) for x in lines[i].split()] for i in (2,3,4)])
    return lattice * scale

def main():
    if not os.path.isfile("POSCAR"):
        print("❌ No reference POSCAR found in this directory.")
        sys.exit(1)

    ref_lat = read_lattice("POSCAR")
    ref_len = np.linalg.norm(ref_lat, axis=1)

    ok, fail = 0, 0
    for fname in sorted(os.listdir()):
        if not fname.startswith("POSCAR_scaled_") or not os.path.isfile(fname):
            continue

        m = pat.match(fname)
        if not m:
            print(f"⚠️  Skipping {fname} (cannot parse scale factors)")
            continue

        sx, sy, sz = map(float, m.groups())
        try:
            lat = read_lattice(fname)
        except Exception as e:
            print(f"⚠️  {fname}: unable to read ({e})")
            fail += 1
            continue

        lengths = np.linalg.norm(lat, axis=1)
        expected = ref_len * np.array([sx, sy, sz])

        print(f"\nChecking {fname}:")
        for i, (orig_len, scale, exp_len, got_len) in enumerate(zip(ref_len, [sx, sy, sz], expected, lengths), 1):
            print(f"  Vector {i}: original length = {orig_len:.6f} Å, scale factor = {scale}, expected length = {exp_len:.6f} Å, actual length = {got_len:.6f} Å")

        if np.all(np.abs(lengths - expected) < TOL):
            print(f"✅ {fname} – scaling correct")
            ok += 1
        else:
            print(f"❌ {fname} – mismatch detected")
            fail += 1

    print(f"\nSummary: {ok} correct, {fail} failed.")
    sys.exit(0 if fail == 0 else 1)

if __name__ == "__main__":
    main()

