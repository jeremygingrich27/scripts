#!/bin/bash

og_dir=$(pwd)

# Get a list of directories in the current directory
dirs=()
i=1
echo "📁 Select a directory from the list below:"
for d in */; do
    if [ -d "$d" ]; then
        echo "  [$i] $d"
        dirs+=("$d")
        ((i++))
    fi
done

# Prompt user to pick one
read -p "Enter the number corresponding to your choice: " choice
selected_dir="${dirs[$((choice - 1))]}"

if [ -z "$selected_dir" ]; then
    echo "❌ Invalid choice."
    exit 1
fi

echo "✅ You selected: $selected_dir"

# Prompt user to enter a sequence of numbers
read -p "Enter a space-separated sequence of numbers: " -a numbers

# Create the parent directory to hold all new numbered directories
container_dir="generated_dirs"
mkdir -p "$container_dir"

echo
echo "📦 All generated directories will be placed inside: $container_dir"
echo "🔁 Looping through the following numbers: ${numbers[*]}"
echo

# Loop over the user-specified numbers
for num in "${numbers[@]}"; do
    echo "➡️  Processing number: $num"

    clean_dir="${selected_dir%/}"
    new_dir="${container_dir}/${num}_${clean_dir}"

    mkdir -p "$new_dir"

    # Copy only selected files from POSCAR_scaled* subdirectories
    for sub in "$selected_dir"/POSCAR_scaled*/; do
        [ -d "$sub" ] || continue
        sub_basename=$(basename "$sub")
        mkdir -p "$new_dir/$sub_basename"

        for file in CHGCAR INCAR KPOINTS POSCAR POTCAR; do
            if [ -f "$sub/$file" ]; then
                cp "$sub/$file" "$new_dir/$sub_basename/"
            fi
        done
    done

    cd "$new_dir" || { echo "❌ Failed to enter $new_dir"; exit 1; }
    bash ~/scripts/structure/editor/loop_scale_factor_changer.sh "$num" "$num" 1
    cd "$og_dir" || exit
done

