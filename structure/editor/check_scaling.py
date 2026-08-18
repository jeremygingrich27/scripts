#!/usr/bin/env python3
"""check_scaling.py — validate the lattice scaling of POSCAR_scaled_* files.

Compares each flat POSCAR_scaled_<sx>_<sy>_<sz> file in the current directory
against a reference POSCAR: each lattice-vector length should equal the
reference length times its scale factor. Exits 0 if all match, 1 otherwise.
"""
import os
import re
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poscar_lib as pl

PAT = re.compile(r"POSCAR_scaled_([\d.]+)_([\d.]+)_([\d.]+)$")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-t", "--tol", type=float, default=1e-3,
                   help="per-vector length tolerance in Å (default: 1e-3)")
    p.add_argument("-r", "--reference", default="POSCAR",
                   help="reference structure (default: POSCAR)")
    a = p.parse_args()

    import numpy as np
    if not os.path.isfile(a.reference):
        sys.exit(f"❌ No reference '{a.reference}' found in this directory.")
    ref_len = pl.lattice_lengths(a.reference)

    ok = fail = 0
    for fname in sorted(os.listdir()):
        if not fname.startswith("POSCAR_scaled_") or not os.path.isfile(fname):
            continue
        m = PAT.match(fname)
        if not m:
            print(f"⚠️  Skipping {fname} (cannot parse scale factors)")
            continue
        scales = np.array([float(x) for x in m.groups()])
        try:
            lengths = pl.lattice_lengths(fname)
        except Exception as e:                   # noqa: BLE001
            print(f"⚠️  {fname}: unable to read ({e})")
            fail += 1
            continue
        expected = ref_len * scales
        if np.all(np.abs(lengths - expected) < a.tol):
            print(f"✅ {fname} – scaling correct")
            ok += 1
        else:
            print(f"❌ {fname} – mismatch (expected {expected}, got {lengths})")
            fail += 1

    print(f"\nSummary: {ok} correct, {fail} failed.")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
