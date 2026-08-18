#!/bin/bash
# Simple and reliable POSCAR/CONTCAR comparison script
# Usage: ./compare_poscar_2_contcar.sh [tolerance]
# Default tolerance: 1e-8

TOLERANCE=${1:-1e-8}
export TOLERANCE

# File existence check
if [[ ! -f POSCAR ]] || [[ ! -f CONTCAR ]]; then
    echo "false"
    exit 1
fi

# If files are identical, return true immediately
if diff POSCAR CONTCAR >/dev/null 2>&1; then
    echo "true"
    exit 0
fi

# Use Python for numerical comparison
python3 - <<'EOF'
import sys
import os

tolerance = float(os.environ.get('TOLERANCE', '1e-8'))

try:
    with open('POSCAR', 'r') as f:
        poscar_lines = f.readlines()
    with open('CONTCAR', 'r') as f:
        contcar_lines = f.readlines()

    if len(poscar_lines) != len(contcar_lines):
        print('false')
        sys.exit(0)

    for i, (p_line, c_line) in enumerate(zip(poscar_lines, contcar_lines)):
        p_line = p_line.strip()
        c_line = c_line.strip()

        # Skip comment line (first line)
        if i == 0:
            continue

        # Skip empty lines
        if not p_line and not c_line:
            continue
        if not p_line or not c_line:
            print('false')
            sys.exit(0)

        try:
            p_nums = [float(x) for x in p_line.split()]
            c_nums = [float(x) for x in c_line.split()]

            if len(p_nums) != len(c_nums):
                print('false')
                sys.exit(0)

            for p_num, c_num in zip(p_nums, c_nums):
                if abs(p_num - c_num) > tolerance * max(1.0, abs(p_num), abs(c_num)):
                    print('false')
                    sys.exit(0)
        except ValueError:
            # Not numerical, do exact string comparison
            if p_line != c_line:
                print('false')
                sys.exit(0)

    print('true')

except Exception:
    print('false')
    sys.exit(1)
EOF

# Ensure a result is printed if Python failed
if [[ $? -ne 0 ]]; then
    echo "false"
fi

