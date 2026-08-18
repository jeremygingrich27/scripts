#!/usr/bin/env python3
"""poscar_scaler.py — scale POSCAR lattice vectors.

Three modes (merges the old poscar_scaler.py and scaling_poscar.py):
  single  scale one POSCAR by 1 or 3 factors
  grid    sweep per-axis ranges (lo hi step) -> all combinations
  batch   read scale factors from a file (one 'sx [sy sz]' per line)

Run with no arguments for an interactive prompt.

Examples
--------
  poscar_scaler.py single POSCAR 1.02                    # uniform +2%
  poscar_scaler.py single POSCAR 1.02 1.0 0.98 -o OUT    # anisotropic
  poscar_scaler.py grid POSCAR --x 0.98 1.02 0.02 --z 0.95 1.05 0.05
  poscar_scaler.py batch POSCAR factors.txt --prefix run
"""
import os
import sys
import argparse
import itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poscar_lib as pl


def frange(lo, hi, step):
    if step == 0:
        return [round(lo, 6)]
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out


def write_scaled(poscar, factors, outname):
    lines = pl.scale_lattice(pl.read_poscar(poscar), factors)
    pl.write_poscar(outname, lines)
    print("Written:", outname)


def make_single(poscar, factors, outname=None):
    factors = list(factors)
    if len(factors) == 1:
        factors *= 3
    elif len(factors) != 3:
        sys.exit("single mode needs 1 or 3 scale factors")
    write_scaled(poscar, factors, outname or f"{poscar}_scaled_{pl.fmt_tag(factors)}")


def make_grid(poscar, x, y, z, prefix=None):
    prefix = prefix or f"{poscar}_scaled"
    for sx, sy, sz in itertools.product(frange(*x), frange(*y), frange(*z)):
        write_scaled(poscar, [sx, sy, sz], f"{prefix}_{pl.fmt_tag([sx, sy, sz])}")


def make_batch(poscar, batch_file, prefix=None):
    prefix = prefix or f"{poscar}_scaled"
    for raw in open(batch_file):
        parts = raw.split()
        if not parts:
            continue
        if len(parts) == 1:
            factors = parts * 3
        elif len(parts) == 3:
            factors = parts
        else:
            print(f"Skipping invalid line: {raw.strip()}", file=sys.stderr)
            continue
        write_scaled(poscar, factors, f"{prefix}_{pl.fmt_tag(factors)}")


def interactive():
    poscar = input("POSCAR filename [POSCAR]: ").strip() or "POSCAR"
    mode = (input("[s]ingle, [g]rid, or [b]atch? ").strip().lower() or "s")[0]
    if mode == "s":
        factors = input("Scale factor(s) (1 or 3 numbers): ").split()
        out = input("Output filename (blank = auto): ").strip() or None
        make_single(poscar, factors, out)
    elif mode == "g":
        print("Enter 'lo hi step' for each axis (blank = 1 1 0, i.e. fixed at 1):")
        def axis(name):
            s = input(f"  {name}: ").split()
            return [float(v) for v in s] if len(s) == 3 else [1.0, 1.0, 0.0]
        x, y, z = axis("X"), axis("Y"), axis("Z")
        prefix = input("Filename prefix (blank = auto): ").strip() or None
        make_grid(poscar, x, y, z, prefix)
    elif mode == "b":
        bf = input("Batch file: ").strip()
        prefix = input("Filename prefix (blank = auto): ").strip() or None
        make_batch(poscar, bf, prefix)
    else:
        sys.exit("unknown mode")


def main():
    if len(sys.argv) == 1:
        interactive()
        return

    p = argparse.ArgumentParser(prog="poscar_scaler.py",
                                description="Scale POSCAR lattice vectors.")
    sub = p.add_subparsers(dest="mode", required=True)

    ps = sub.add_parser("single", help="scale by 1 or 3 factors")
    ps.add_argument("poscar")
    ps.add_argument("factors", nargs="+", help="1 factor (uniform) or 3 (per axis)")
    ps.add_argument("-o", "--output", help="output filename (default: auto)")

    pg = sub.add_parser("grid", help="sweep per-axis ranges")
    pg.add_argument("poscar")
    pg.add_argument("--x", nargs=3, type=float, metavar=("LO", "HI", "STEP"), default=[1.0, 1.0, 0.0])
    pg.add_argument("--y", nargs=3, type=float, metavar=("LO", "HI", "STEP"), default=[1.0, 1.0, 0.0])
    pg.add_argument("--z", nargs=3, type=float, metavar=("LO", "HI", "STEP"), default=[1.0, 1.0, 0.0])
    pg.add_argument("--prefix", help="output filename prefix (default: auto)")

    pb = sub.add_parser("batch", help="read factors from a file")
    pb.add_argument("poscar")
    pb.add_argument("batch_file")
    pb.add_argument("--prefix", help="output filename prefix (default: auto)")

    a = p.parse_args()
    if a.mode == "single":
        # allow a trailing non-numeric token to be treated as the output name
        factors, out = a.factors, a.output
        if out is None and len(factors) in (2, 4):
            out = factors[-1]
            factors = factors[:-1]
        make_single(a.poscar, factors, out)
    elif a.mode == "grid":
        make_grid(a.poscar, a.x, a.y, a.z, a.prefix)
    elif a.mode == "batch":
        make_batch(a.poscar, a.batch_file, a.prefix)


if __name__ == "__main__":
    main()
