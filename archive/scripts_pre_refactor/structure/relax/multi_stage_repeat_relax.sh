#!/bin/bash
# VASP relaxation script with multi-stage ISIF/IBRION parameters
# Usage: bash repeat_relax.sh [tolerance] (ISIF1,IBRION1) (ISIF2,IBRION2) ... (ISIF_final,IBRION_final)
# Example: bash repeat_relax.sh 1e-6 (3,2) (1,3)

MAX_ITER=50
ITER=0
LOG_FILE="relaxation.log"
OUTPUT_DIR="relaxation_outputs"
STAGE=1
TOLERANCE="1e-6"  # Default tolerance

# Check if first argument is a tolerance value
if [[ $1 =~ ^[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$ ]]; then
    TOLERANCE="$1"
    shift  # Remove tolerance from arguments
fi

# Parse command line arguments for (ISIF,IBRION) pairs
STAGES=()
for arg in "$@"; do
    # Accept both (ISIF,IBRION) and ISIF:IBRION formats
    if [[ $arg =~ ^\(([0-9]+),([0-9]+)\)$ ]]; then
        isif="${BASH_REMATCH[1]}"
        ibrion="${BASH_REMATCH[2]}"
        STAGES+=("$isif,$ibrion")
    elif [[ $arg =~ ^([0-9]+):([0-9]+)$ ]]; then
        isif="${BASH_REMATCH[1]}"
        ibrion="${BASH_REMATCH[2]}"
        STAGES+=("$isif,$ibrion")
    else
        echo "Error: Invalid argument format '$arg'. Use (ISIF,IBRION) or ISIF:IBRION format."
        echo "Example: bash $0 [tolerance] \"(3,2)\" \"(1,3)\" or bash $0 [tolerance] 3:2 1:3"
        exit 1
    fi
done

# Check if at least one stage is provided
if [[ ${#STAGES[@]} -eq 0 ]]; then
    echo "Error: No valid (ISIF,IBRION) pairs provided."
    echo "Usage: bash $0 [tolerance] \"(ISIF1,IBRION1)\" \"(ISIF2,IBRION2)\" ..."
    echo "Alternative: bash $0 [tolerance] ISIF1:IBRION1 ISIF2:IBRION2 ..."
    echo "Example: bash $0 1e-6 \"(3,2)\" \"(1,3)\" or bash $0 1e-6 3:2 1:3"
    exit 1
fi

# Check for required files
for file in POSCAR INCAR; do
    if [[ ! -f "$file" ]]; then
        echo "Error: Required file $file not found"
        exit 1
    fi
done

# Check if comparison script exists
COMPARE_SCRIPT="$HOME/scripts/structure/relax/compare_poscar_contcar.sh"
if [[ ! -f "$COMPARE_SCRIPT" ]]; then
    # Try to find it in current directory or PATH
    if command -v compare_poscar_contcar.sh >/dev/null 2>&1; then
        COMPARE_SCRIPT="compare_poscar_contcar.sh"
    else
        echo "Error: compare_poscar_contcar.sh script not found"
        echo "Please ensure the script is in your PATH or update the COMPARE_SCRIPT variable"
        exit 1
    fi
fi

# Check if VASP command is available
VASP_CMD="vasp_std"
if command -v ibrun >/dev/null 2>&1; then
    VASP_CMD="ibrun vasp_std"
elif ! command -v vasp_std >/dev/null 2>&1; then
    echo "Error: VASP executable not found. Please ensure vasp_std is in your PATH"
    exit 1
fi

# Backup original INCAR
cp INCAR INCAR.original

# Cleanup function
cleanup() {
    if [[ -f INCAR.original ]]; then
        mv INCAR.original INCAR
        echo "Restored original INCAR"
    fi
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Function to update INCAR with new ISIF and IBRION values
update_incar() {
    local isif=$1
    local ibrion=$2

    # Create temporary INCAR
    cp INCAR.original INCAR.tmp

    # Update or add ISIF
    if grep -q "^[[:space:]]*ISIF" INCAR.tmp; then
        sed -i "s/^[[:space:]]*ISIF[[:space:]]*=.*/ISIF   = $isif/" INCAR.tmp
    else
        echo "ISIF   = $isif" >> INCAR.tmp
    fi

    # Update or add IBRION
    if grep -q "^[[:space:]]*IBRION" INCAR.tmp; then
        sed -i "s/^[[:space:]]*IBRION[[:space:]]*=.*/IBRION = $ibrion/" INCAR.tmp
    else
        echo "IBRION = $ibrion" >> INCAR.tmp
    fi

    # Replace INCAR with updated version
    mv INCAR.tmp INCAR
}

# Initialize logging and directories
mkdir -p "$OUTPUT_DIR"
{
    echo "VASP Multi-Stage Relaxation Log - $(date)"
    echo "Tolerance: $TOLERANCE"
    echo "Stages: ${STAGES[*]}"
    echo "Final stage will be repeated until convergence"
    echo "========================================"
    printf "%-6s %-8s %-15s %-10s %s\n" "Iter" "Stage" "Energy(eV)" "ISIF/IBRION" "Status"
    echo "========================================"
} > "$LOG_FILE"

# Initialize final status variables
final_energy="N/A"
final_isif="N/A"
final_ibrion="N/A"
final_converged=false

# Process all stages
for stage_idx in "${!STAGES[@]}"; do
    IFS=',' read -r current_isif current_ibrion <<< "${STAGES[$stage_idx]}"
    final_isif="$current_isif"
    final_ibrion="$current_ibrion"

    # Update INCAR for current stage
    update_incar "$current_isif" "$current_ibrion"

    echo "Stage $((stage_idx + 1)): ISIF=$current_isif, IBRION=$current_ibrion" | tee -a "$LOG_FILE"

    # Determine if this is the final stage (will be repeated)
    is_final_stage=$((stage_idx == ${#STAGES[@]} - 1))

    if [[ $is_final_stage -eq 1 ]]; then
        # Final stage: repeat until convergence
        stage_converged=false
        stage_iter=0

        while (( ITER < MAX_ITER && stage_converged == false )); do
            ((ITER++))
            ((stage_iter++))

            # Run VASP
            $VASP_CMD > vasp.out 2>&1
            if [[ $? -ne 0 ]]; then
                echo "$ITER VASP failed" >> "$LOG_FILE"
                break
            fi

            # Check for CONTCAR
            if [[ ! -f CONTCAR ]]; then
                echo "$ITER CONTCAR missing" >> "$LOG_FILE"
                break
            fi

            # Create iteration directory
            iter_dir="$OUTPUT_DIR/iter_$ITER"
            mkdir -p "$iter_dir"
            cp {POSCAR,CONTCAR,OUTCAR,OSZICAR,INCAR} "$iter_dir/" 2>/dev/null

            # Extract energy
            energy=$(grep "free  energy   TOTEN" OUTCAR | tail -1 | awk '{print $5}')
            energy=${energy:-N/A}
            final_energy="$energy"

            # Compare structures for convergence
            result=$(bash "$COMPARE_SCRIPT" "$TOLERANCE")
            if [[ "$result" != "true" && "$result" != "false" ]]; then
                echo "$ITER Comparison failed" >> "$LOG_FILE"
                break
            fi

            # Log status
            status=$([[ "$result" == "true" ]] && echo "CONVERGED" || echo "CONTINUE")
            printf "%-6d %-8s %-15s %-10s %s\n" "$ITER" "$((stage_idx + 1))" "$energy" "$current_isif/$current_ibrion" "$status" >> "$LOG_FILE"

            # Check convergence for final stage
            if [[ "$result" == "true" ]]; then
                stage_converged=true
                final_converged=true
                break
            fi

            # Update POSCAR for next iteration
            cp CONTCAR POSCAR
        done

    else
        # Non-final stage: run once
        ((ITER++))

        # Run VASP
        $VASP_CMD > vasp.out 2>&1
        if [[ $? -ne 0 ]]; then
            echo "$ITER VASP failed" >> "$LOG_FILE"
            break
        fi

        # Check for CONTCAR
        if [[ ! -f CONTCAR ]]; then
            echo "$ITER CONTCAR missing" >> "$LOG_FILE"
            break
        fi

        # Create iteration directory
        iter_dir="$OUTPUT_DIR/iter_$ITER"
        mkdir -p "$iter_dir"
        cp {POSCAR,CONTCAR,OUTCAR,OSZICAR,INCAR} "$iter_dir/" 2>/dev/null

        # Extract energy
        energy=$(grep "free  energy   TOTEN" OUTCAR | tail -1 | awk '{print $5}')
        energy=${energy:-N/A}
        final_energy="$energy"

        # Log status (no convergence check for non-final stages)
        printf "%-6d %-8s %-15s %-10s %s\n" "$ITER" "$((stage_idx + 1))" "$energy" "$current_isif/$current_ibrion" "STAGE_COMPLETE" >> "$LOG_FILE"

        # Update POSCAR for next stage
        cp CONTCAR POSCAR
    fi
done

# Final status
{
    echo "========================================"
    if [[ "$final_converged" == "true" ]]; then
        echo "Converged after $ITER total iterations"
    else
        echo "Stopped after $ITER total iterations"
    fi
    echo "Final energy: $final_energy eV"
    echo "Final parameters: ISIF=$final_isif, IBRION=$final_ibrion"
    echo "Tolerance used: $TOLERANCE"
} | tee -a "$LOG_FILE"

echo "Multi-stage relaxation completed. Check $LOG_FILE for details."
