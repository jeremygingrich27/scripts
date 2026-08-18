#!/bin/bash

# Load the template into an array
TEMPLATE_FILE="$HOME/scripts/util/templates/INCAR.template"
if [[ ! -f "$TEMPLATE_FILE" ]]; then
    echo "Template file '$TEMPLATE_FILE' not found."
    exit 1
fi

# Autodetect number of species from POSCAR if available
if [[ -f POSCAR ]]; then
    num_species=$(awk 'NR==6 {for (i=1;i<=NF;i++) sum+=$i; print sum}' POSCAR)
    species_counts=($(awk 'NR==6 {for (i=1;i<=NF;i++) print $i}' POSCAR))
    num_species_fields=${#species_counts[@]}
else
    echo "Warning: POSCAR file not found. Cannot autodetect number of species."
    num_species_fields=0
fi

mapfile -t lines < "$TEMPLATE_FILE"

# Extract block indices and names
declare -A block_indices
block_count=0
for i in "${!lines[@]}"; do
    if [[ "${lines[$i]}" =~ ^#\ \[(.*)\]\ (.*)$ ]]; then
        block_indices[$block_count]=$i
        echo "[$block_count] ${BASH_REMATCH[2]}"
        ((block_count++))
    fi
done

# Ask user for which blocks to include
echo "Enter the indices of the blocks you want to include (space separated):"
read -r selected
selected_array=($selected)

# Create output INCAR
OUTFILE="INCAR"
> "$OUTFILE"

for idx in "${selected_array[@]}"; do
    start_index=${block_indices[$idx]}
    next_block=$((idx+1))
    if [[ $next_block -lt $block_count ]]; then
        end_index=${block_indices[$next_block]}
    else
        end_index=${#lines[@]}
    fi

    echo "# ${lines[$start_index]#\# }" >> "$OUTFILE"

    for ((j=start_index+1; j<end_index; j++)); do
        line="${lines[$j]}"
        tag=$(echo "$line" | awk '{print $1}')
        dtype=$(echo "$line" | awk '{print $3}')

        if [[ -z "$tag" || "$tag" == \#* ]]; then
            continue
        fi

        case $dtype in
            BOOL)
                while true; do
                    read -rp "Set $tag (TRUE/FALSE): " val
                    if [[ "$val" =~ ^(TRUE|FALSE)$ ]]; then
                        echo "$tag = .$val." >> "$OUTFILE"
                        break
                    else
                        echo "Invalid input. Enter TRUE or FALSE."
                    fi
                done
                ;;
            INT)
                while true; do
                    read -rp "Set $tag (integer): " val
                    if [[ "$val" =~ ^-?[0-9]+$ ]]; then
                        echo "$tag = $val" >> "$OUTFILE"
                        break
                    else
                        echo "Invalid integer."
                    fi
                done
                ;;
            FLOAT)
                while true; do
                    read -rp "Set $tag (float): " val
                    if [[ "$val" =~ ^-?[0-9]*\.?[0-9]+$ ]]; then
                        echo "$tag = $val" >> "$OUTFILE"
                        break
                    else
                        echo "Invalid float."
                    fi
                done
                ;;
            SPECIES_INT)
                echo "Detected $num_species_fields species from POSCAR."
                while true; do
                    read -rp "Set $tag (space-separated $num_species_fields integers): " val
                    val_array=($val)
                    if [[ ${#val_array[@]} -eq $num_species_fields && "$val" =~ ^([0-9]+[[:space:]]*)+$ ]]; then
                        echo "$tag = $val" >> "$OUTFILE"
                        break
                    else
                        echo "Invalid input. Provide $num_species_fields integers."
                    fi
                done
                ;;
            SPECIES_FLOAT)
                echo "Detected $num_species_fields species from POSCAR."
                while true; do
                    read -rp "Set $tag (space-separated $num_species_fields floats): " val
                    val_array=($val)
                    valid=true
                    for x in "${val_array[@]}"; do
                        if ! [[ "$x" =~ ^-?[0-9]*\.?[0-9]+$ ]]; then
                            valid=false
                            break
                        fi
                    done
                    if [[ ${#val_array[@]} -eq $num_species_fields && "$valid" == true ]]; then
                        echo "$tag = $val" >> "$OUTFILE"
                        break
                    else
                        echo "Invalid input. Provide $num_species_fields floats."
                    fi
                done
                ;;
            *)
                read -rp "Set $tag (value): " val
                echo "$tag = $val" >> "$OUTFILE"
                ;;
        esac
    done

    echo "" >> "$OUTFILE"
done

echo "Generated INCAR file based on your selections."

