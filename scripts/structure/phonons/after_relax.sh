#!/bin/bash
# Script to setup phonons directory from converged relaxation calculation

# Check if phonons_INCAR exists in current directory
if [[ ! -f "phonons_INCAR" ]]; then
    echo "Error: phonons_INCAR not found in current directory" >&2
    echo "false"
    exit 1
fi

# Check if relax directory exists
if [[ ! -d "relax" ]]; then
    echo "Error: relax directory not found" >&2
    echo "false"
    exit 1
fi

relax_log="relax/relaxation.log"

# Check if relaxation.log exists
if [[ ! -f "$relax_log" ]]; then
    echo "Error: relaxation.log not found in relax directory" >&2
    echo "false"
    exit 1
fi

# Check if the calculation converged in two ways:
# 1. Look for "CONVERGED" in the log file
# 2. Run the structure comparison directly
converged_in_log=$(grep -q "CONVERGED" "$relax_log" && echo "true" || echo "false")

# Check structure comparison directly
cd relax
structure_converged=$(bash ~/scripts/structure/relax/compare_poscar_contcar.sh 2>/dev/null)
cd ..

if [[ "$converged_in_log" == "true" ]] || [[ "$structure_converged" == "true" ]]; then
    if [[ "$converged_in_log" == "true" ]]; then
        echo "Found converged calculation in relax directory (from log)"
    else
        echo "Found converged calculation in relax directory (from structure comparison)"
    fi
    
    # Create phonons directory in current directory
    phonons_dir="phonons"
    mkdir -p "$phonons_dir"
    
    # Required files to copy from relax directory
    files_to_copy=("CHGCAR" "WAVECAR" "POTCAR")
    missing_files=()
    
    # Copy required files
    for file in "${files_to_copy[@]}"; do
        if [[ -f "relax/$file" ]]; then
            cp "relax/$file" "$phonons_dir/"
            echo "  Copied $file"
        else
            missing_files+=("$file")
        fi
    done

    # Copy CONTCAR as POSCAR
    if [[ -f "relax/CONTCAR" ]]; then
        cp "relax/CONTCAR" "$phonons_dir/POSCAR"
        echo "  Copied CONTCAR as POSCAR"
    else
        missing_files+=("CONTCAR")
    fi

    # Copy phonons_INCAR as INCAR
    cp "phonons_INCAR" "$phonons_dir/INCAR"
    echo "  Copied phonons_INCAR as INCAR"
    
    # Report any missing files
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        echo "  Warning: Missing files in relax directory: ${missing_files[*]}" >&2
    fi
    
    echo "  Phonons setup complete in $phonons_dir"
    echo "true"
else
    echo "Relaxation not converged" >&2
    echo "false"
fi
