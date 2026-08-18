#!/usr/bin/env python3
import sys
import itertools
from pathlib import Path

# ──────────────────────────────────────────────────────────────────── helpers ──

def read_poscar(fname):
    # Keep line endings so formatting is preserved on write
    return Path(fname).read_text().splitlines(keepends=True)

def write_poscar(fname, lines):
    # Write all lines as-is, including newlines
    Path(fname).write_text("".join(lines))

def scale_lattice(lines, factors):
    # factors must be floats
    factors = list(map(float, factors))
    # Lines 2,3,4 (0-based: 2,3,4) are lattice vectors, scale them
    for i in range(3):
        vec = list(map(float, lines[i+2].split()))
        # Format each component with 16 decimal places, keep spacing aligned by adding two spaces at start
        lines[i+2] = "  " + "  ".join(f"{x*factors[i]:.16f}" for x in vec) + lines[i+2][len(lines[i+2].rstrip()):]  # preserve trailing whitespace/newlines
    return lines

def fmt_name(factors):
    # Format scaling factors into filename-friendly string like '1_1_0.8'
    parts = []
    for f in factors:
        s = f"{float(f):.3f}"
        s = s.rstrip('0').rstrip('.') if '.' in s else s
        parts.append(s)
    return "_".join(parts)

# ───────────────────────────────────────────────────────────── single routine ──

def make_single(poscar, factors, outname=None):
    if len(factors) == 1:
        factors *= 3
    elif len(factors) != 3:
        sys.exit("Need 1 or 3 scale factors for single mode.")

    if outname is None:
        outname = f"{poscar}_scaled_{fmt_name(factors)}"

    lines = read_poscar(poscar)
    scaled_lines = scale_lattice(lines, factors)
    write_poscar(outname, scaled_lines)
    print("Written", outname)

# ─────────────────────────────────────────────────────────── multiple routine ──

def frange(fmin, fmax, step):
    if step == 0:
        return [round(fmin, 6)]
    vals = []
    v = fmin
    while v <= fmax + 1e-9:
        vals.append(round(v, 6))
        v += step
    return vals

def make_multiple(poscar, mins, maxs, incs, prefix=None):
    xs = frange(mins[0], maxs[0], incs[0])
    ys = frange(mins[1], maxs[1], incs[1])
    zs = frange(mins[2], maxs[2], incs[2])

    prefix = prefix or f"{poscar}_scaled"
    for sx, sy, sz in itertools.product(xs, ys, zs):
        tag = fmt_name([sx, sy, sz])
        name = f"{prefix}_{tag}"
        lines = read_poscar(poscar)
        scaled_lines = scale_lattice(lines, [sx, sy, sz])
        write_poscar(name, scaled_lines)
        print("Written", name)

# ──────────────────────────────────────────────────────────────── main logic ──

def main():
    if len(sys.argv) == 1:  # interactive mode
        poscar = input("POSCAR filename: ").strip() or "POSCAR"
        mode = input("Make [s]ingle or [m]ultiple scaled POSCARs? ").lower()
        if mode.startswith('s'):
            factors = input("Scale factor(s) (1 or 3 numbers): ").split()
            outn = input("Output file name (blank = auto): ").strip() or None
            make_single(poscar, factors, outn)
        else:  # multiple
            print("Enter min, max, increment for X, Y, Z")
            xmin, xmax, incx = map(float, input("X: ").split())
            ymin, ymax, incy = map(float, input("Y: ").split())
            zmin, zmax, incz = map(float, input("Z: ").split())
            prefix = input("Filename prefix (blank = POSCAR_scaled): ").strip() or None
            make_multiple(poscar,
                          [xmin, ymin, zmin], [xmax, ymax, zmax], [incx, incy, incz],
                          prefix)
        return

    # command line mode
    if len(sys.argv) < 4:
        print("CLI usage:")
        print("  single  : scale_poscar.py POSCAR single sx [sy sz] [OUTPUT]")
        print("  multiple: scale_poscar.py POSCAR multiple xmin ymin zmin xmax ymax zmax incx incy incz [--prefix P]")
        sys.exit(1)

    poscar, mode, *rest = sys.argv[1:]
    mode = mode.lower()

    if mode.startswith('s'):
        if len(rest) in (1, 2, 3):
            # If last argument looks like a filename (contains a dot or no digit?), treat it as output filename?
            # Your original logic:
            factors = rest[:-1] if len(rest) in (2, 4) else rest
            outn = rest[-1] if len(rest) in (2, 4) else None
            make_single(poscar, factors, outn)
        else:
            sys.exit("single mode expects: sx [sy sz] [OUTPUT]")

    elif mode.startswith('m'):
        if '--prefix' in rest:
            pidx = rest.index('--prefix')
            prefix = rest[pidx + 1]
            rest = rest[:pidx]
        else:
            prefix = None
        if len(rest) != 9:
            sys.exit("multiple mode needs 9 numbers: xmin ymin zmin xmax ymax zmax incx incy incz")
        nums = list(map(float, rest))
        make_multiple(poscar,
                      nums[0:3], nums[3:6], nums[6:9], prefix)
    else:
        sys.exit("Mode must be 'single' or 'multiple'.")

if __name__ == "__main__":
    main()

