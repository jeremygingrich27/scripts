#!/bin/bash
# loop_extract_files.sh — Batch-Extract Archive Files
#
# Prerequisites
# -------------
#   - bash 4+
#   - tar  (standard on all Unix/Linux systems)
#
# Usage
# -----
#   Place this script in a directory containing one or more archive files
#   and run:
#
#     bash loop_extract_files.sh
#
#   Supported formats: .tar  .tar.gz  .tar.bz2  .tar.xz  .tgz
#
#   Each archive is extracted in-place.  Progress is printed for every
#   file.  If an extraction fails, an error message is printed and the
#   script continues with remaining archives.

# ---------------------------------------------------------------------------
# Extract each archive found in the current directory
# ---------------------------------------------------------------------------
found=0
for file in *.tar *.tar.gz *.tar.bz2 *.tar.xz *.tgz; do
    # Skip if the glob matched nothing (literal filename, not a real file)
    [[ -f "$file" ]] || continue
    found=1
    echo "Extracting: $file"
    tar -xf "$file" || echo "[FAIL] Failed to extract: $file"
done

if [[ $found -eq 0 ]]; then
    echo "No archive files found in $(pwd)." >&2
    exit 1
fi
