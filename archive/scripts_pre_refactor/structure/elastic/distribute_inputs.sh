#!/usr/bin/env bash
# distribute_inputs_to_strains.sh
# --------------------------------------------------------------
# Usage:   ./distribute_inputs_to_strains.sh  [FILE1 FILE2 ...]
# If no FILE arguments are given, the script links INCAR KPOINTS POTCAR.
#
# For every   */strain_*   directory it will:
#   • ln -sfn  <relative‑path‑to‑FILE>  strain_dir/FILE
#     (overwrites any existing link or file of that name)
#
# Requires:   bash 4+, coreutils (realpath)

set -euo pipefail

# -------- files to distribute ----------
if (( $# )); then
    FILES=("$@")
else
    FILES=(INCAR KPOINTS POTCAR)
fi

ROOT=$(pwd)

echo "⏳ Scanning for strain_* directories under $ROOT ..."
mapfile -t STRAIN_DIRS < <(find . -type d -name "strain_*" | sort)

if ((${#STRAIN_DIRS[@]} == 0)); then
    echo "❌  No strain_* directories found. Exiting."
    exit 1
fi
echo "📂 Found ${#STRAIN_DIRS[@]} strain directories."

# -------- main loop ----------
for dir in "${STRAIN_DIRS[@]}"; do
    for file in "${FILES[@]}"; do
        src="$ROOT/$file"
        if [[ ! -e $src ]]; then
            echo "⚠️  $src not found; skipped for $dir"
            continue
        fi
        relpath=$(realpath --relative-to="$dir" "$src")
        ln -sfn "$relpath" "$dir/$file"
        echo "   → $dir/$file  →  $relpath"
    done
done

echo -e "\n✅  Finished linking files to all strain directories."

