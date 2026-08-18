#!/usr/bin/env bash
# make_disp_interactive.sh
# Interactively runs make_disp_line_arg.sh in every POSCAR*/ subdirectory.
#
# Usage:
#   bash make_disp_interactive.sh
#
# Run from the directory that contains POSCAR*/ subdirectories.
# For each subdirectory the script enters it, generates phonopy displacements,
# and optionally copies extra files alongside the defaults (INCAR, KPOINTS, POTCAR).

set -euo pipefail

SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Find POSCAR* subdirectories
mapfile -t dirs < <(find . -maxdepth 1 -type d -name "POSCAR*" | sort)

if [[ ${#dirs[@]} -eq 0 ]]; then
    echo "No POSCAR* directories found in current directory."
    exit 1
fi

echo "Found ${#dirs[@]} POSCAR* directories:"
printf '  %s\n' "${dirs[@]}"
echo "----------------------------------------"

read -rp "Copy extra files beyond defaults (INCAR KPOINTS POTCAR)? (y/n): " answer
EXTRA_ARGS=()
if [[ $answer =~ ^[Yy]$ ]]; then
    read -rp "Enter extra file names (space-separated): " -a extra_files
    EXTRA_ARGS=(--cp "${extra_files[@]}")
fi

for dir in "${dirs[@]}"; do
    dir="${dir#./}"
    echo "Entering directory: $dir"
    cd "$dir" || { echo "Failed to enter $dir"; exit 1; }

    bash "$SCRIPT_DIR/make_disp_line_arg.sh" "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

    echo "Finished processing $dir"
    echo "----------------------------------------"
    cd ..
done

echo "All directories processed."
