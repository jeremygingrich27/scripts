#!/usr/bin/env python3
import sys
import os

def read_poscar(filename):
    with open(filename, 'r') as f:
        return f.readlines()

def write_poscar(filename, lines):
    with open(filename, 'w') as f:
        f.writelines(lines)

def scale_lattice(poscar_lines, scale_factors):
    for i in range(3):
        vec = list(map(float, poscar_lines[i + 2].split()))
        scaled_vec = [f"{x * scale_factors[i]:.16f}" for x in vec]
        poscar_lines[i + 2] = "  " + "  ".join(scaled_vec) + "\n"
    return poscar_lines

def scale_a(ratio):
    return (1.0 / ratio) ** (1.0 / 3.0)

def scale_b(ratio):
    return scale_a(ratio)

def scale_c(ratio):
    return scale_a(ratio) * ratio

def format_tag(ratio):
    tag = f"{ratio:.3f}".rstrip('0').rstrip('.') if '.' in f"{ratio:.3f}" else f"{ratio:.3f}"
    return tag

def main():
    if len(sys.argv) != 3:
        print("Usage: scale_poscar_c_by_a.py <POSCAR_file> <ratios_file>")
        sys.exit(1)

    poscar_file = sys.argv[1]
    ratios_file = sys.argv[2]

    if not os.path.isfile(poscar_file):
        print(f"Error: POSCAR file '{poscar_file}' not found.")
        sys.exit(1)

    if not os.path.isfile(ratios_file):
        print(f"Error: Ratios file '{ratios_file}' not found.")
        sys.exit(1)

    with open(ratios_file, 'r') as f:
        ratios = [float(line.strip()) for line in f if line.strip()]

    for ratio in ratios:
        a = scale_a(ratio)
        b = scale_b(ratio)
        c = scale_c(ratio)
        scales = [a, b, c]

        tag = format_tag(ratio)
        output_file = f"{os.path.basename(poscar_file)}_scaled_{tag}"

        poscar_lines = read_poscar(poscar_file)
        scaled_lines = scale_lattice(poscar_lines, scales)
        write_poscar(output_file, scaled_lines)

        print(f"Wrote: {output_file} (c/a = {ratio}, a = {a:.6f}, c = {c:.6f})")

if __name__ == "__main__":
    main()

