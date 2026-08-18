#!/usr/bin/env python3
import sys

def read_poscar(filename):
    with open(filename, 'r') as f:
        return f.readlines()

def write_poscar(filename, lines):
    with open(filename, 'w') as f:
        f.writelines(lines)

def scale_lattice(poscar_lines, scale_factors):
    scale_factors = list(map(float, scale_factors))
    for i in range(3):
        vec = list(map(float, poscar_lines[i + 2].split()))
        scaled_vec = [f"{x * scale_factors[i]:.16f}" for x in vec]
        poscar_lines[i + 2] = "  " + "  ".join(scaled_vec) + "\n"
    return poscar_lines

def format_scale_name(scale_factors):
    """Format scale factors for filename (e.g. 1.02_1.02_1.02)"""
    return "_".join([f"{float(s):.3f}".rstrip('0').rstrip('.') if '.' in f"{float(s):.3f}" else f"{float(s):.3f}" for s in scale_factors])

def run_single(poscar_file, scale_factors, output_file=None):
    if len(scale_factors) == 1:
        scale_factors *= 3
    elif len(scale_factors) != 3:
        print("Error: Provide either 1 or 3 scale factors.")
        sys.exit(1)

    if output_file is None:
        tag = format_scale_name(scale_factors)
        output_file = f"{poscar_file}_scaled_{tag}"

    lines = read_poscar(poscar_file)
    scaled = scale_lattice(lines, scale_factors)
    write_poscar(output_file, scaled)
    print(f"Written: {output_file}")

def run_batch(poscar_file, batch_file, prefix=None):
    with open(batch_file, 'r') as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) == 1:
            scale_factors = parts * 3
        elif len(parts) == 3:
            scale_factors = parts
        else:
            print(f"Skipping invalid line: {line.strip()}")
            continue

        tag = format_scale_name(scale_factors)
        base = prefix if prefix else f"{poscar_file}_scaled"
        output_file = f"{base}_{tag}"

        poscar_lines = read_poscar(poscar_file)
        scaled = scale_lattice(poscar_lines, scale_factors)
        write_poscar(output_file, scaled)
        print(f"Written: {output_file}")

def main():
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  Single: scale_poscar.py <POSCAR> <scale | sx sy sz> [output_file]")
        print("  Batch:  scale_poscar.py --batch <POSCAR> <batch_file> [--prefix PREFIX]")
        sys.exit(1)

    if args[0] == "--batch":
        if len(args) < 3:
            print("Usage: scale_poscar.py --batch <POSCAR> <batch_file> [--prefix PREFIX]")
            sys.exit(1)

        poscar_file = args[1]
        batch_file = args[2]
        prefix = args[4] if len(args) == 5 and args[3] == "--prefix" else None

        run_batch(poscar_file, batch_file, prefix)

    else:
        if len(args) not in [2, 4]:
            print("Usage: scale_poscar.py <POSCAR> <scale | sx sy sz> [output_file]")
            sys.exit(1)

        poscar_file = args[0]
        scale_factors = args[1:-1] if len(args) == 4 else args[1:]
        output_file = args[-1] if len(args) == 4 else None
        run_single(poscar_file, scale_factors, output_file)

if __name__ == "__main__":
    main()

