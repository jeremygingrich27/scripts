#!/usr/bin/env bash
# Usage: ./collect_calcs.sh ARG
# Finds directories named ARG whose OUTCAR contains:
# "General timing and accounting informations for this job:"
# Copies them into ./ARG, preserving their original relative paths
# Excludes CHG, CHGCAR, vasprun.xml, WAVECAR, XDATCAR

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <directory_name>"
    exit 1
fi

ARG="$1"
DEST_DIR="./$ARG"

mkdir -p "$DEST_DIR"

find . -type d -name "$ARG" | while read -r dir; do
    # Skip destination dir itself
    if [[ "$dir" == "$DEST_DIR" ]]; then
        continue
    fi
    
    OUTCAR="$dir/OUTCAR"
    
    # Check OUTCAR
    if [[ -f "$OUTCAR" ]] && grep -q "General timing and accounting informations for this job:" "$OUTCAR"; then
        echo "Copying $dir -> $DEST_DIR"

        # Remove leading "./" for cleaner paths
        rel_path="${dir#./}"

        # Create matching parent path inside DEST_DIR
        mkdir -p "$DEST_DIR/$(dirname "$rel_path")"

        # Copy into its own preserved path
        rsync -av \
            --exclude="CHG" \
            --exclude="CHGCAR" \
            --exclude="WAVECAR" \
            "$dir" "$DEST_DIR/$(dirname "$rel_path")"
    else
        echo "Skipping $dir (no matching OUTCAR)"
    fi
done

