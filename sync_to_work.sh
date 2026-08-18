#!/usr/bin/env bash
# sync_to_work.sh — Copy a completed VASP job directory from $SCRATCH to $WORK
#
# Run this at the end of each jobscript, or manually after jobs complete.
#
# Usage (from jobscript):
#   bash ${HOME}/scripts/sync_to_work.sh "${SCRATCH}/Research/Crystal_Systems/CuO/AFII/phonons"
#
# Usage (manual, from the job directory):
#   bash ${HOME}/scripts/sync_to_work.sh "$(pwd)"
#
# The destination mirrors the source path under $WORK, so the directory
# structure on $WORK matches $SCRATCH automatically.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <source_directory>" >&2
    exit 1
fi

SOURCE="$(realpath "$1")"

if [[ ! -d "${SOURCE}" ]]; then
    echo "Error: source directory does not exist: ${SOURCE}" >&2
    exit 1
fi

# Build destination path: replace $SCRATCH prefix with $WORK
if [[ "${SOURCE}" == "${SCRATCH}"* ]]; then
    DEST="${WORK}${SOURCE#${SCRATCH}}"
else
    # If not under $SCRATCH, mirror relative to $WORK/Research
    DEST="${WORK}/Research/$(basename "${SOURCE}")"
    echo "Warning: source is not under \$SCRATCH, syncing to ${DEST}" >&2
fi

echo "Syncing: ${SOURCE}"
echo "     to: ${DEST}"
echo ""

mkdir -p "${DEST}"

rsync -av --progress \
    --include="INCAR" \
    --include="POSCAR" \
    --include="POSCAR-*" \
    --include="CONTCAR" \
    --include="KPOINTS" \
    --include="SPOSCAR" \
    --include="jobscript" \
    --include="*.sh" \
    --include="*.py" \
    --include="OUTCAR" \
    --include="OSZICAR" \
    --include="REPORT" \
    --include="COMPLETED" \
    --include="vasprun.xml" \
    --include="FORCE_SETS" \
    --include="phonopy.yaml" \
    --include="band.yaml" \
    --include="HIGH_SYMMETRY_POINTS" \
    --include="KPATH.phonopy" \
    --include="SYMMETRY" \
    --include="*.dat" \
    --include="*.csv" \
    --include="*.json" \
    --include="*.png" \
    --include="*.log" \
    --include="README*" \
    --include="*/" \
    --exclude="*" \
    "${SOURCE}/" \
    "${DEST}/"

echo ""
echo "Done. Files saved to \$WORK at:"
echo "  ${DEST}"
