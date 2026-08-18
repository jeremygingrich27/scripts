#!/bin/bash

phonopy -d --dim 1 1 1 --pa auto

# Default files to copy (INCAR, KPOINTS, POTCAR)
FILES_TO_COPY=("INCAR" "KPOINTS" "POTCAR")

# Parse command-line arguments for extra files
EXTRA_FILES=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cp)
            shift
            while [[ $# -gt 0 && ! "$1" == --* ]]; do
                EXTRA_FILES+=("$1")
                shift
            done
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Combine default and extra files
FILES_TO_COPY+=("${EXTRA_FILES[@]}")

echo "Files to copy to each directory: ${FILES_TO_COPY[*]}"

# Find all POSCAR-* files
POSCAR_FILES=(POSCAR-*)
if [[ ${#POSCAR_FILES[@]} -eq 0 ]]; then
    echo "No POSCAR-* files found in current directory."
    exit 0
fi

echo "Found ${#POSCAR_FILES[@]} POSCAR-* files"

# Process each POSCAR file
for poscar in "${POSCAR_FILES[@]}"; do
    # Extract directory name (e.g., "001" from "POSCAR-001")
    dir_name="${poscar#POSCAR-}"

    # Create directory if it doesn't exist
    if [[ ! -d "$dir_name" ]]; then
        mkdir -v "$dir_name"
    fi

    # Copy POSCAR file (renamed to just POSCAR in the new directory)
    mv -v "$poscar" "$dir_name/POSCAR"

    # Copy other files
    for file in "${FILES_TO_COPY[@]}"; do
        if [[ -f "$file" ]]; then
            cp -v "$file" "$dir_name/"
        else
            echo "Warning: $file not found - skipping"
        fi
    done
done

echo "Done!"
