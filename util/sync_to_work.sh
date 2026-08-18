#!/usr/bin/env bash
# sync_to_work.sh
# Copy a VASP calculation directory to $WORK on Lonestar6, excluding files not
# needed to rerun or plot (WAVECAR, CHG, XDATCAR, PCDAT, REPORT, *.err/*.out).
# If source_dir is omitted, the current directory is used.
set -uo pipefail

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && {
    echo "Usage: $(basename "$0") [source_dir]   (mirror source_dir to \$WORK/<name>)"
    exit 0
}

: "${WORK:?WORK is not set — this script is for TACC where \$WORK points to the work filesystem}"
SOURCE="$(realpath "${1:-.}")"
DEST="${WORK}/$(basename "$SOURCE")"

echo "Source : $SOURCE"
echo "Dest   : $DEST"
echo

rsync -av --progress \
    --exclude='WAVECAR' \
    --exclude='CHG' \
    --exclude='XDATCAR' \
    --exclude='PCDAT' \
    --exclude='REPORT' \
    --exclude='*.err' \
    --exclude='*.out' \
    "${SOURCE}/" \
    "${DEST}/"
