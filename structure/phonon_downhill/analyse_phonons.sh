#!/usr/bin/env bash
# After all displacements finished: force constants, mode labels, unstable multiplet, directions.
#
# usage: analyse_phonons.sh PHONON_DIR
# Last line printed: STABLE ... or UNSTABLE ... (from soft_modes.py).
set -e
ph=$1
source "$DH/downhill.conf"
cd "$ph"

# forces -> FORCE_SETS -> FORCE_CONSTANTS, traditional (the symfc projector ignores MAGMOM)
# (phonopy v4: -f lives in phonopy-init)
phonopy-init -f disp-*/vasprun.xml > forces.log 2>&1
phonopy phonopy_disp.yaml --writefc --full-fc --fc-calc traditional > writefc.log 2>&1

# labels from crystal-utilities (spinless parent of this structure)
crystal basis POSCAR -o symmetry > symmetry_basis.log 2>&1 || echo "crystal basis failed; modes unlabelled"
if [[ -f symmetry/symmetry_basis ]]; then
    crystal modes . --code phonopy --asr --basis symmetry -o crystal_modes
else
    crystal modes . --code phonopy --asr -o crystal_modes
fi

# unstable multiplet (also cross-checked against crystal modes below)
result=$(python3 "$DH/soft_modes.py" . "$THRESHOLD" "$DEGEN_TOL" | tee soft_modes.log | tail -1)
echo "$result" > SOFT_MODES
if [[ $result == UNSTABLE* ]]; then
    f=$(echo "$result" | awk '{print $3}')
    # the same frequency must appear in crystal modes' table; take its label
    label=$(awk -v f="$f" '$1 ~ /^[0-9]+$/ && NF >= 8 && ($2 - f)^2 < 1e-6 {print $NF; exit}' crystal_modes/modes.txt)
    [[ -z $label ]] && { echo "frequency $f not found in crystal modes: check" ; exit 1; }
    [[ $label =~ ^[0-9.eE+-]+$ ]] && label=mode     # unlabelled table: last column is a number
    python3 "$DH/find_directions.py" . "$label" "$SYMPREC" > find_directions.log
fi
echo "$result"
