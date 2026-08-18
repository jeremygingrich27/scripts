#!/usr/bin/env python3
"""ca_ratio_volume_constant.py — generate scaled POSCARs that vary the c/a ratio
while keeping the cell volume constant.

For each ratio r (one per line in the ratios file): a,b scale by (1/r)^(1/3) and
c scales by (1/r)^(1/3) * r, so the volume a*b*c is preserved.
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poscar_lib as pl


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("poscar", help="reference POSCAR/CONTCAR")
    p.add_argument("ratios_file", help="text file with one c/a ratio per line")
    a = p.parse_args()

    if not os.path.isfile(a.poscar):
        sys.exit(f"Error: POSCAR '{a.poscar}' not found")
    if not os.path.isfile(a.ratios_file):
        sys.exit(f"Error: ratios file '{a.ratios_file}' not found")

    ratios = [float(x) for x in open(a.ratios_file) if x.strip()]
    for r in ratios:
        sa = (1.0 / r) ** (1.0 / 3.0)
        scales = [sa, sa, sa * r]                      # volume-preserving
        tag = pl.fmt_tag([r])
        out = f"{os.path.basename(a.poscar)}_scaled_{tag}"
        pl.write_poscar(out, pl.scale_lattice(pl.read_poscar(a.poscar), scales))
        print(f"Wrote: {out}  (c/a={r}, a-scale={sa:.6f}, c-scale={sa * r:.6f})")


if __name__ == "__main__":
    main()
