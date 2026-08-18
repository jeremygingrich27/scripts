#!/usr/bin/env bash
# write_jobscript.sh
set -euo pipefail

# Function to scan for directories with VASP input files
find_vasp_directories() {
    local dirs=()
    for dir in */; do
        if [[ -f "$dir/POSCAR" && -f "$dir/POTCAR" && -f "$dir/KPOINTS" ]]; then
            dirs+=("$dir")
        fi
    done
    echo "${dirs[@]}"
}

# Function to select VASP directory
select_vasp_directory() {
    echo "Scanning for directories with VASP input files..."
    
    # Find directories with required VASP files
    local vasp_dirs=($(find_vasp_directories))
    
    if [ ${#vasp_dirs[@]} -eq 0 ]; then
        echo "No directories containing POSCAR, POTCAR, and KPOINTS found."
        return 1
    elif [ ${#vasp_dirs[@]} -eq 1 ]; then
        # Only one directory found, use it automatically
        SELECTED_DIR="${vasp_dirs[0]%/}"
        echo "Found one directory with VASP files: $SELECTED_DIR"
        return 0
    else
        # Multiple directories found, ask user to choose
        echo "Found multiple directories with VASP input files:"
        for i in "${!vasp_dirs[@]}"; do
            echo "$((i+1)). ${vasp_dirs[i]%/}"
        done
        
        while true; do
            read -rp "Please select a directory (1-${#vasp_dirs[@]}), or press Enter to skip: " choice
            if [[ -z "$choice" ]]; then
                return 1
            elif [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le ${#vasp_dirs[@]} ]; then
                SELECTED_DIR="${vasp_dirs[$((choice-1))]%/}"
                echo "Selected directory: $SELECTED_DIR"
                return 0
            else
                echo "Invalid selection. Please enter a number between 1 and ${#vasp_dirs[@]}."
            fi
        done
    fi
}

echo

# Check for VASP directories and offer selection
SELECTED_DIR=""
if select_vasp_directory; then
    echo "VASP directory selected: $SELECTED_DIR"
    echo
fi

read -rp "Enter calc name [test]: " CALC
CALC=${CALC:-test}
read -rp "Enter # of nodes [1]: " NODES
NODES=${NODES:-1}
read -rp "Enter # of cores [16]: " CORES
CORES=${CORES:-16}
read -rp "Enter queue name [vm-small]: " QUEUE
QUEUE=${QUEUE:-vm-small}
read -rp "Enter job length [00:30:00]: " TIME
TIME=${TIME:-00:30:00}
read -rp "Enter project name [PHY24018]: " PROJECT
PROJECT=${PROJECT:-PHY24018}
echo
###############################################################################
# 1. Write the base jobscript header
###############################################################################
cat > jobscript <<EOF
#!/bin/bash
#SBATCH -J ${CALC}
#SBATCH -o ${CALC}_%j.out
#SBATCH -e ${CALC}_%j.err
#SBATCH -N ${NODES}
#SBATCH -n ${CORES}
#SBATCH -p ${QUEUE}
#SBATCH -t ${TIME}
#SBATCH -A ${PROJECT}
module purge
module load intel/19.1.1  impi/19.0.9
module load vasp/6.3.0
export OMP_NUM_THREADS=1
start_time=\$(date +%s)
CURRENT_DIR=\$(pwd)
EOF
###############################################################################
# 2. Offer optional snippet additions
###############################################################################
ADDITIONS_DIR="$HOME/scripts/jobs/additional_functions"
if [ -d "$ADDITIONS_DIR" ] && compgen -G "$ADDITIONS_DIR"/* >/dev/null; then
    echo
    echo "Optional jobscript additions found in: $ADDITIONS_DIR"
    mapfile -t ADDITION_FILES < <(ls -1 "$ADDITIONS_DIR"/*)
    for i in "${!ADDITION_FILES[@]}"; do
        printf "  %2d) %s\n" "$((i + 1))" "$(basename "${ADDITION_FILES[i]}")"
    done
    echo
    read -rp "Enter numbers to append (e.g. 1 3 4), or press <Enter> for none: " CHOICES
    echo
    for idx in $CHOICES; do
        if [[ "$idx" =~ ^[0-9]+$ ]] && (( idx>=1 && idx<=${#ADDITION_FILES[@]} )); then
            ADDITION_FILE="${ADDITION_FILES[idx-1]}"
            echo ">>> Appending $(basename "$ADDITION_FILE")"
            
            # Read the addition file content and replace original_directory if needed
            ADDITION_CONTENT=$(cat "$ADDITION_FILE")
            if [[ -n "$SELECTED_DIR" ]]; then
                ADDITION_CONTENT="${ADDITION_CONTENT//original_directory/$SELECTED_DIR}"
            fi
            
            {
                printf "# ===== Begin %s =====\n" "$(basename "$ADDITION_FILE")"
                echo "$ADDITION_CONTENT"
                printf "cd \"\$CURRENT_DIR\"\n"
                printf "# ===== End %s =====\n\n"   "$(basename "$ADDITION_FILE")"
            } >> jobscript
        else
            echo ">>> Skipping invalid selection: '$idx'"
        fi
    done
else
    echo "No snippet files found in $ADDITIONS_DIR – skipping optional additions."
fi
###############################################################################
# 3. Write the base jobscript footer
###############################################################################
cat >> jobscript <<EOF
status=\$?
end_time=\$(date +%s)
elapsed=\$((end_time - start_time))
echo "Job completed in \$elapsed seconds"
exit \$status
EOF
echo -e "\n✅ Jobscript written to ./jobscript"
