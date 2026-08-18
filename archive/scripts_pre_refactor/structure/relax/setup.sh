#!/bin/bash

# Check if directory argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <directory>"
    echo "Example: $0 input_files/"
    exit 1
fi

# Check if relax directory already exists
if [ -d "relax" ]; then
    echo "Relax directory already exists. Doing nothing."
    exit 0
fi

original_dir="$1"

# Remove trailing slash if present for consistency
original_dir="${original_dir%/}"

# Check if directory exists
if [ ! -d "$original_dir" ]; then
    echo "Error: Directory '$original_dir' does not exist."
    exit 1
fi

# Check if required VASP input files exist in the directory
if [[ ! -f "$original_dir/POSCAR" || ! -f "$original_dir/POTCAR" || ! -f "$original_dir/KPOINTS" ]]; then
    echo "Error: Directory '$original_dir' does not contain all required files (POSCAR, POTCAR, KPOINTS)."
    exit 1
fi

# Copy the directory to 'relax'
cp -r "$original_dir" "relax"

# Copy relaxation INCAR
incar_file="relax_INCAR"
if [ -f "$incar_file" ]; then
    cp "$incar_file" "relax/INCAR"
else
    echo "Error: $incar_file not found."
    exit 1
fi

echo "Relaxation directory setup completed."
