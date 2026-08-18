#!/usr/bin/env bash
# make_disp_line_arg.sh
# Run `phonopy -d` to generate displacement POSCAR-* files, then move each into a
# numbered subdirectory along with the VASP input files. Run from a phonons/ dir
# containing POSCAR, INCAR, KPOINTS, POTCAR.
set -euo pipefail

usage() {
    cat <<USAGE
Usage: $(basename "$0") [--cp FILE1 FILE2 ...]

Generates phonopy displacements and organizes them into POSCAR-* subdirectories.
Default files copied into each: INCAR KPOINTS POTCAR.

  --cp FILE...   extra files to copy into each displacement directory
  -h, --help     show this help and exit
USAGE
}

FILES_TO_COPY=("INCAR" "KPOINTS" "POTCAR")
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cp)
            shift
            while [[ $# -gt 0 && "$1" != --* ]]; do FILES_TO_COPY+=("$1"); shift; done
            ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

phonopy -d --dim 1 1 1 --pa auto

echo "Files copied to each directory: ${FILES_TO_COPY[*]}"
shopt -s nullglob
POSCAR_FILES=(POSCAR-*)
(( ${#POSCAR_FILES[@]} > 0 )) || { echo "No POSCAR-* files generated."; exit 0; }
echo "Found ${#POSCAR_FILES[@]} POSCAR-* files"

for poscar in "${POSCAR_FILES[@]}"; do
    dir_name="${poscar#POSCAR-}"
    mkdir -p "$dir_name"
    mv "$poscar" "$dir_name/POSCAR"
    for file in "${FILES_TO_COPY[@]}"; do
        if [[ -f "$file" ]]; then
            cp "$file" "$dir_name/"
        else
            echo "Warning: $file not found - skipping"
        fi
    done
done
echo "Done!"
