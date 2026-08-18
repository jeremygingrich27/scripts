#!/usr/bin/env bash

current_dir=$(pwd)
base_dir="vary_inplane_lattice"
phonon_base_dir="varied_phonons"

# Check that the directory exists
if [[ ! -d "$base_dir" ]]; then
    echo "Directory '$base_dir' not found in $current_dir"
    exit 1
fi

# Check that phonons_base template exists
if [[ ! -d "phonons_base" ]]; then
    echo "phonons_base template directory not found in $current_dir"
    exit 1
fi

echo "Setting up phonon calculations for energy minima..."

# Loop through each subdirectory in vary_inplane_lattice
for subdir in "$base_dir"/*/; do
    [[ -d "$subdir" ]] || continue

    # Get clean subdirectory name (e.g., "scale_0.95")
    subdir_name=$(basename "$subdir")
    echo "Processing subdirectory: $subdir_name"

    # Run Python script and capture the output as an array
    # Only look for actual directories, not tar.gz files
    echo "  Finding energy minima in ${subdir}vary_inplane_lattice_scale_*"

    # Capture stderr for diagnostics and stdout for actual results
    python_output=$(python3 ~/scripts/util/energy_minima.py "${subdir}vary_inplane_lattice_scale_*" 2>&1)
    python_exit_code=$?

    # Separate stdout from stderr
    mapfile -t minima_dirs < <(python3 ~/scripts/util/energy_minima.py "${subdir}vary_inplane_lattice_scale_*" 2>/dev/null)

    # Show diagnostic messages
    python3 ~/scripts/util/energy_minima.py "${subdir}vary_inplane_lattice_scale_*" >/dev/null

    if [[ ${#minima_dirs[@]} -eq 0 ]]; then
        echo "  No minima found for $subdir_name, skipping..."
        continue
    fi

    echo "  Found ${#minima_dirs[@]} minima directories"

    # Create phonon directory for this subdir - FIX: Use explicit path construction
    phonon_dir="${current_dir}/${phonon_base_dir}/${subdir_name}"
    mkdir -p "$phonon_dir"
    echo "  Created phonon directory: $phonon_dir"

    # Process each minimum
    for poscar_dir in "${minima_dirs[@]}"; do
        # Skip empty lines and any non-POSCAR entries
        [[ -n "$poscar_dir" ]] || continue
        [[ "$poscar_dir" =~ ^POSCAR_z_ ]] || continue

        echo "    Preparing phonons for minimum: $poscar_dir"

        # Create phonon calculation directory
        phonon_calc_dir="$phonon_dir/${poscar_dir}"
        cp -r "./phonons_base" "$phonon_calc_dir"

        # Process each ISIF directory in the phonon calculation template
        for isif_dir in "$phonon_calc_dir"/*/; do
            [[ -d "$isif_dir" ]] || continue

            isif_name=$(basename "$isif_dir")
            echo "      Setting up $isif_name"

            # Source directory with the optimized structure
            # The POSCAR_z_* directories are at the same level as vary_inplane_lattice_scale_X.XX
            source_dir="${subdir}${poscar_dir}"

            # Target directory within the ISIF calculation
            target_dir="$isif_dir/base_POSCAR"
            mkdir -p "$target_dir"

            # Copy required files
            files_to_copy=("POSCAR" "POTCAR" "KPOINTS" "CHGCAR")
            files_copied=0

            for file in "${files_to_copy[@]}"; do
                if [[ -f "$source_dir/$file" ]]; then
                    cp "$source_dir/$file" "$target_dir/"
                    echo "        Copied $file"
                    ((files_copied++))
                else
                    echo "        Warning: $file not found in $source_dir"
                fi
            done

            if [[ $files_copied -eq 0 ]]; then
                echo "        ERROR: No files could be copied for $poscar_dir in $isif_name"
            fi
        done
    done

    echo "  Completed setup for $subdir_name"
    echo ""
done

echo "Phonon calculation setup complete!"
echo ""
echo "Summary of created directories:"
find . -name "varied_phonons" -type d | sort

echo ""
echo "Checking for successful setups (directories with copied files):"
for phonon_dir in varied_phonons; do
    [[ -d "$phonon_dir" ]] || continue
    echo "Directory: $phonon_dir"

    for calc_dir in "$phonon_dir"/*/; do
        [[ -d "$calc_dir" ]] || continue
        calc_name=$(basename "$calc_dir")

        for isif_dir in "$calc_dir"/*/; do
            [[ -d "$isif_dir" ]] || continue
            isif_name=$(basename "$isif_dir")

            file_count=$(find "$isif_dir" -name "POSCAR" -o -name "POTCAR" -o -name "KPOINTS" -o -name "CHGCAR" | wc -l)
            if [[ $file_count -gt 0 ]]; then
                echo "  $calc_name/$isif_name: $file_count files copied"
            fi
        done
    done
done
