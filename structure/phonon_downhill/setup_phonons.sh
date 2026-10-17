#!/usr/bin/env bash
# Create the phonopy displacements for one round and one VASP dir per displacement.
#
# usage: setup_phonons.sh PHONON_DIR INPUTS_DIR
#   PHONON_DIR must already hold POSCAR (the structure of this round).
#   INPUTS_DIR holds INCAR.sp, KPOINTS, POTCAR, MAGMOM (phonopy format "MAGMOM = ...").
set -e
ph=$1; in=$2
source "$DH/downhill.conf"
cd "$ph"
cp "$in/MAGMOM" MAGMOM

cat > disp.conf <<EOF
DIM = 1 1 1
CREATE_DISPLACEMENTS = .TRUE.
DISPLACEMENT_DISTANCE = $DISPLACEMENT
$(cat MAGMOM)
EOF

phonopy-init disp.conf > phonopy_disp.log 2>&1    # phonopy v4: setup is phonopy-init; reads POSCAR; MAGMOM must be in the conf file

for p in POSCAR-*; do
    d=disp-${p#POSCAR-}
    mkdir -p "$d"
    cp "$p" "$d/POSCAR"
    cp "$in/INCAR.sp" "$d/INCAR"
    cp "$in/KPOINTS" "$in/POTCAR" "$d/"
done
echo "$(ls -d disp-* | wc -l) displacements in $ph"
