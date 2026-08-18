#!/usr/bin/env python3
"""change_scaling_factors.py — replace line 2 (the scale factor line) of a POSCAR
with three values X Y Z. Edits the file in place (default: ./POSCAR)."""
import sys
import argparse
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("x")
    p.add_argument("y")
    p.add_argument("z")
    p.add_argument("-f", "--file", default="POSCAR",
                   help="POSCAR file to edit in place (default: POSCAR)")
    a = p.parse_args()

    path = Path(a.file)
    if not path.is_file():
        sys.exit(f"Error: '{a.file}' not found")
    lines = path.read_text().splitlines(keepends=True)
    if len(lines) < 2:
        sys.exit(f"Error: '{a.file}' has too few lines to be a POSCAR")
    lines[1] = f"{a.x} {a.y} {a.z}\n"
    path.write_text("".join(lines))
    print(f"Set scale-factor line of {a.file} to: {a.x} {a.y} {a.z}")


if __name__ == "__main__":
    main()
