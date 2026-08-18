#!/bin/bash
# Simple and reliable POSCAR/CONTCAR comparison script
TOLERANCE=1e-8

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

# Use a simple Python script for numerical comparison
python3 -c "
import sys
import os

tolerance = float(os.environ.get('TOLERANCE', '1e-6'))

try:
    with open('POSCAR', 'r') as f:
        poscar_lines = f.readlines()
    with open('CONTCAR', 'r') as f:
        contcar_lines = f.readlines()
    
    if len(poscar_lines) != len(contcar_lines):
        print('false')
        sys.exit(0)
    
    # Check each line
    for i, (p_line, c_line) in enumerate(zip(poscar_lines, contcar_lines)):
        p_line = p_line.strip()
        c_line = c_line.strip()
        
        # Skip comment line (first line)
        if i == 0:
            continue
            
        # Try to parse as numbers
        try:
            p_nums = [float(x) for x in p_line.split()]
            c_nums = [float(x) for x in c_line.split()]
            
            if len(p_nums) != len(c_nums):
                if p_line != c_line:
                    print('false')
                    sys.exit(0)
            else:
                # Numerical comparison
                for p_num, c_num in zip(p_nums, c_nums):
                    if abs(p_num - c_num) > tolerance:
                        print('false')
                        sys.exit(0)
        except ValueError:
            # Not numerical, do string comparison
            if p_line != c_line:
                print('false')
                sys.exit(0)
    
    print('true')
    
except Exception:
    print('false')
    sys.exit(1)
" 2>/dev/null

if [[ $? -ne 0 ]]; then
    echo "false"
fi
