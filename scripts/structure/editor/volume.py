#!/usr/bin/env python3
import sys
import numpy as np

def read_lattice_vectors(poscar_file):
    with open(poscar_file, 'r') as f:
        lines = f.readlines()
        a = np.array(list(map(float, lines[2].split())))
        b = np.array(list(map(float, lines[3].split())))
        c = np.array(list(map(float, lines[4].split())))
    return a, b, c

def compute_volume(a, b, c):
    return abs(np.dot(a, np.cross(b, c)))

def main():
    if len(sys.argv) != 2:
        print("Usage: get_poscar_volume.py <POSCAR file>")
        sys.exit(1)

    poscar_file = sys.argv[1]

    try:
        a, b, c = read_lattice_vectors(poscar_file)
        volume = compute_volume(a, b, c)
        print(f"Volume of unit cell: {volume:.6f} Å³")
    except Exception as e:
        print(f"Error reading POSCAR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

