#!/bin/bash

read -p "Enter supercell dimensions X Y Z (e.g. 2 2 2): " X Y Z

# Step 0: Detect correct INCAR path
TOPDIR=$(realpath "$(dirname "$PWD")")
BASE_INCAR="$TOPDIR/INCARs/base_INCAR"

if [[ ! -f "$BASE_INCAR" ]]; then
    echo "❌ base_INCAR not found at $BASE_INCAR"
    exit 1
fi

# Step 1: Make a timestamped backup
parent_dir=$(basename "$PWD")
timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
backup_dir="../${parent_dir}_backup_$timestamp"

echo "📦 Backing up current directory to $backup_dir"
mkdir -p "$backup_dir"
rsync -a --exclude="$backup_dir" . "$backup_dir"
echo "✅ Backup complete."

# Step 2: Extract MAGMOM (if present)
MAGMOM_LINE=$(awk 'toupper($1) == "MAGMOM" {
    for (i=2; i<=NF; i++) printf "%s ", $i;
    print ""
}' "$BASE_INCAR" | sed 's/ *= */ /g' | xargs)

HAS_MAGMOM=0
if [[ -n "$MAGMOM_LINE" ]]; then
    HAS_MAGMOM=1
    echo "📌 Found MAGMOM in base_INCAR: $MAGMOM_LINE"
fi

# Loop through each POSCAR_* directory
for d in POSCAR_*/; do
    echo "🔧 Processing $d"
    cd "$d" || continue

    atom_count=$(awk 'NR==7 {for (i=1;i<=NF;i++) sum+=$i; print sum}' POSCAR)
    magmom_count=$(wc -w <<< "$MAGMOM_LINE")

    # Run phonopy
    if [[ "$HAS_MAGMOM" -eq 1 && "$magmom_count" -eq "$atom_count" ]]; then
        phonopy -d --dim "$X" "$Y" "$Z" --magmom $MAGMOM_LINE
    else
        if [[ "$HAS_MAGMOM" -eq 1 ]]; then
            echo "⚠️  Skipping --magmom: mismatch between atom count ($atom_count) and MAGMOM count ($magmom_count)"
        fi
        phonopy -d --dim "$X" "$Y" "$Z"
    fi

    # Always copy base_INCAR
    cp "$BASE_INCAR" INCAR

    # If phonopy generated MAGMOM, insert it into INCAR
    if [[ -f MAGMOM ]]; then
        awk 'BEGIN{done=0}
            toupper($1) == "MAGMOM" && !done {
                while ((getline line < "MAGMOM") > 0) print "MAGMOM = " line;
                done=1; next
            }
            {print}
            END {
                if (!done && (getline line < "MAGMOM") > 0) {
                    print "MAGMOM = " line
                    while ((getline line) > 0) print line
                }
            }
        ' "$BASE_INCAR" > INCAR.tmp && mv INCAR.tmp INCAR

    else
        echo "⚠️  MAGMOM file not generated — guessing based on species"

        species=($(awk 'NR==6 {for(i=1;i<=NF;i++) print $i}' POSCAR))
        counts=($(awk 'NR==7 {for(i=1;i<=NF;i++) print $i}' POSCAR))
        guessed=()
        for i in "${!species[@]}"; do
            s="${species[$i]}"
            n="${counts[$i]}"
            moment=${default_moments[$s]:-0}
            for ((j=0; j<n; j++)); do
                guessed+=("$moment")
            done
        done
        echo "MAGMOM = ${guessed[*]}" >> INCAR
    fi

    # Replace POSCAR with SPOSCAR
    if [[ -f SPOSCAR ]]; then
        mv POSCAR POSCAR.unit
        mv SPOSCAR POSCAR
    else
        echo "⚠️  SPOSCAR not found"
    fi

    rm -f POSCAR-*
    cd ..
done

echo "🎉 All POSCAR_* folders processed successfully."

