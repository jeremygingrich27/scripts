#!/usr/bin/env bash
# super_cell_maker.sh
# For every POSCAR_*/ subdirectory: build a phonopy supercell, inject MAGMOM
# (from ../INCARs/base_INCAR if present), replace POSCAR with SPOSCAR, and write
# an INCAR. Run from the directory containing the POSCAR_*/ subdirectories.
set -uo pipefail   # not -e: per-directory tools may fail; loop continues

usage() {
    cat <<USAGE
Usage: $(basename "$0") [X Y Z]

Supercell dimensions X Y Z may be given as arguments or entered interactively.
Requires ../INCARs/base_INCAR (one level up from the current directory).

  -h, --help   show this help and exit
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

if [[ $# -eq 3 ]]; then
    X="$1"; Y="$2"; Z="$3"
elif [[ $# -eq 0 ]]; then
    read -rp "Enter supercell dimensions X Y Z (e.g. 2 2 2): " X Y Z
else
    usage >&2; exit 1
fi
[[ "$X" =~ ^[0-9]+$ && "$Y" =~ ^[0-9]+$ && "$Z" =~ ^[0-9]+$ ]] || { echo "ERROR: X Y Z must be integers" >&2; exit 1; }

# Optional per-species fallback moments for the "no MAGMOM" case (edit as needed).
declare -A default_moments=()

TOPDIR=$(realpath "$(dirname "$PWD")")
BASE_INCAR="$TOPDIR/INCARs/base_INCAR"
[[ -f "$BASE_INCAR" ]] || { echo "❌ base_INCAR not found at $BASE_INCAR" >&2; exit 1; }

# Timestamped backup of the current directory.
parent_dir=$(basename "$PWD")
backup_dir="../${parent_dir}_backup_$(date +%Y-%m-%d_%H-%M-%S)"
echo "📦 Backing up to $backup_dir"
mkdir -p "$backup_dir"
rsync -a --exclude="$(basename "$backup_dir")" . "$backup_dir"

# Extract a MAGMOM line from base_INCAR (if any).
MAGMOM_LINE=$(awk 'toupper($1)=="MAGMOM"{for(i=2;i<=NF;i++)printf "%s ",$i; print ""}' "$BASE_INCAR" | sed 's/ *= */ /g' | xargs)
HAS_MAGMOM=0
[[ -n "$MAGMOM_LINE" ]] && { HAS_MAGMOM=1; echo "📌 base_INCAR MAGMOM: $MAGMOM_LINE"; }

shopt -s nullglob
for d in POSCAR_*/; do
    echo "🔧 $d"
    cd "$d" || continue

    atom_count=$(awk 'NR==7{for(i=1;i<=NF;i++)s+=$i; print s}' POSCAR)
    magmom_count=$(wc -w <<< "$MAGMOM_LINE")

    if (( HAS_MAGMOM && magmom_count == atom_count )); then
        phonopy -d --dim "$X" "$Y" "$Z" --magmom $MAGMOM_LINE
    else
        (( HAS_MAGMOM )) && echo "⚠️  Skipping --magmom: atom count ($atom_count) != MAGMOM count ($magmom_count)"
        phonopy -d --dim "$X" "$Y" "$Z"
    fi

    cp "$BASE_INCAR" INCAR
    if [[ -f MAGMOM ]]; then
        awk 'BEGIN{done=0}
            toupper($1)=="MAGMOM" && !done { while((getline line < "MAGMOM")>0) print "MAGMOM = " line; done=1; next }
            {print}
            END { if(!done && (getline line < "MAGMOM")>0){ print "MAGMOM = " line; while((getline line)>0) print line } }
        ' "$BASE_INCAR" > INCAR.tmp && mv INCAR.tmp INCAR
    else
        echo "⚠️  No MAGMOM file generated — using per-species fallback moments"
        species=($(awk 'NR==6{for(i=1;i<=NF;i++)print $i}' POSCAR))
        counts=($(awk 'NR==7{for(i=1;i<=NF;i++)print $i}' POSCAR))
        guessed=()
        for i in "${!species[@]}"; do
            moment="${default_moments[${species[$i]}]:-0}"
            for ((j=0; j<counts[i]; j++)); do guessed+=("$moment"); done
        done
        echo "MAGMOM = ${guessed[*]}" >> INCAR
    fi

    if [[ -f SPOSCAR ]]; then
        mv POSCAR POSCAR.unit
        mv SPOSCAR POSCAR
    else
        echo "⚠️  SPOSCAR not found"
    fi
    rm -f POSCAR-*
    cd ..
done
echo "🎉 All POSCAR_* folders processed."
