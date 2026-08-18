#!/usr/bin/env python3
"""
POSCAR lattice parameter parser
Usage: python3 parse_poscar.py <POSCAR_file>
Outputs: A_length B_length C_length (in Angstroms)
"""

import sys
import numpy as np

def parse_poscar(filename):
    """Parse POSCAR file and return lattice lengths in Angstroms."""
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Remove any empty lines and strip whitespace
        lines = [line.strip() for line in lines if line.strip()]
        
        if len(lines) < 5:
            raise ValueError(f"POSCAR file too short: {len(lines)} lines")
        
        # Line 1: Comment (skip)
        # Line 2: Scale factor(s)
        scale_line = lines[1].split()
        
        if len(scale_line) == 1:
            # Single scale factor for all directions
            sx = sy = sz = float(scale_line[0])
        elif len(scale_line) == 3:
            # Three scale factors
            sx, sy, sz = map(float, scale_line)
        else:
            raise ValueError(f"Invalid scale factor line: {lines[1]}")
        
        # Lines 3-5: Lattice vectors
        lattice_vectors = []
        for i in range(2, 5):  # lines[2], lines[3], lines[4]
            vector = list(map(float, lines[i].split()[:3]))  # Take first 3 numbers
            if len(vector) != 3:
                raise ValueError(f"Invalid lattice vector on line {i+1}: {lines[i]}")
            lattice_vectors.append(vector)
        
        # Convert to numpy array for easier manipulation
        lattice = np.array(lattice_vectors)
        
        # Apply scale factors
        scaled_lattice = lattice * np.array([sx, sy, sz])
        
        # Calculate lengths
        a_len = np.linalg.norm(scaled_lattice[0])
        b_len = np.linalg.norm(scaled_lattice[1])
        c_len = np.linalg.norm(scaled_lattice[2])
        
        return a_len, b_len, c_len
        
    except (IOError, OSError) as e:
        raise RuntimeError(f"Error reading file {filename}: {e}")
    except (ValueError, IndexError) as e:
        raise RuntimeError(f"Error parsing POSCAR file {filename}: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 parse_poscar.py <POSCAR_file>", file=sys.stderr)
        sys.exit(1)
    
    filename = sys.argv[1]
    
    try:
        a_len, b_len, c_len = parse_poscar(filename)
        # Output format: A_length B_length C_length
        print(f"{a_len:.6f} {b_len:.6f} {c_len:.6f}")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
