#!/usr/bin/env bash
# pull_from_tacc.sh — Sync research data from TACC $WORK to local machine
#
# Usage:
#   ./pull_from_tacc.sh              # sync everything
#   ./pull_from_tacc.sh CuO/AFII    # sync a specific subdirectory
#
# Pulls inputs, processed results, and large outputs (OUTCAR, vasprun.xml)
# from TACC $WORK. Run this after a batch of jobs completes.

set -euo pipefail

TACC_USER="jerging27"
TACC_HOST="ls6.tacc.utexas.edu"

# $WORK on LS6 — update this if your allocation number changes
# Find it with: ssh ls6 'echo $WORK'
TACC_WORK="/work/$(ssh ${TACC_USER}@${TACC_HOST} 'echo ${WORK##/work/}' 2>/dev/null || echo '10070/jerging27/ls6')"
TACC_RESEARCH="${TACC_USER}@${TACC_HOST}:${TACC_WORK}/Research/Crystal_Systems"

LOCAL_DIR="${HOME}/Research/Crystal_Systems"

# Optional: sync only a subdirectory (e.g. CuO/AFII)
SUBDIR="${1:-}"

# Files excluded from git but worth keeping locally for analysis
# (synced here but not committed to the Research git repo)
LARGE_OUTPUTS=(
    "--include=OUTCAR"
    "--include=vasprun.xml"
)

rsync -avz --progress \
    "${LARGE_OUTPUTS[@]}" \
    --exclude="CHGCAR" \
    --exclude="WAVECAR" \
    --exclude="CHG" \
    --exclude="DOSCAR" \
    --exclude="EIGENVAL" \
    --exclude="IBZKPT" \
    --exclude="PCDAT" \
    --exclude="PROCAR" \
    --exclude="XDATCAR" \
    --exclude="TMPCAR" \
    --exclude="POTCAR" \
    --exclude="*.tar.gz" \
    --exclude="*.tar.bz2" \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    "${TACC_RESEARCH}/${SUBDIR}" \
    "${LOCAL_DIR}/${SUBDIR}"

echo ""
echo "Sync complete. To commit new inputs/results to git:"
echo "  cd ~/Research && git add -p && git commit"
