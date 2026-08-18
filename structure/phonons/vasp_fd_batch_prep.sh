#!/usr/bin/env bash
# vasp_fd_batch_prep.sh
# Generate a phonon band path (QPOINTS) in every POSCAR*/ directory using
# vaspkit option 303. Run from the directory containing the POSCAR*/ subdirs.
set -uo pipefail

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && {
    echo "Usage: $(basename "$0")   (run vaspkit 303 -> QPOINTS in each POSCAR*/ dir)"
    exit 0
}

shopt -s nullglob
dirs=(POSCAR*/)
(( ${#dirs[@]} > 0 )) || { echo "No POSCAR*/ directories found." >&2; exit 1; }

for dir in "${dirs[@]}"; do
    echo "🔍 $dir"
    ( cd "$dir" && echo -e "303" | vaspkit && mv -f KPATH.in QPOINTS ) \
        || echo "  ⚠️  failed in $dir"
done
echo "✅ Done."
