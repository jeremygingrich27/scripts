#!/usr/bin/env python3
"""volume.py — print the unit-cell volume (Å³) of a POSCAR/CONTCAR."""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poscar_lib as pl


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("poscar", help="POSCAR/CONTCAR file")
    a = p.parse_args()
    try:
        print(f"Volume of unit cell: {pl.cell_volume(a.poscar):.6f} Å³")
    except Exception as e:                       # noqa: BLE001
        sys.exit(f"Error reading POSCAR '{a.poscar}': {e}")


if __name__ == "__main__":
    main()
