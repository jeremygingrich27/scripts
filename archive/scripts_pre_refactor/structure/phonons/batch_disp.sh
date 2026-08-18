#!/bin/bash

# Find all POSCAR* directories and store them in an array
dirs=( $(find . -maxdepth 1 -type d -name "POSCAR*" | sort) )

# Check if any directories were found
if [ ${#dirs[@]} -eq 0 ]; then
    echo "No POSCAR* directories found in current directory."
    exit 1
fi

echo "Found ${#dirs[@]} POSCAR* directories:"
printf '%s\n' "${dirs[@]}"
echo "----------------------------------------"

# Ask user if they want to copy files
read -p "Copy files? (y/n) " answer
if [[ $answer =~ ^[Yy]$ ]]; then
    COPY=true
    read -p "Enter names of files to copy (space separated): " -a files_to_copy
else
    COPY=false
fi

# Loop through each directory
for dir in "${dirs[@]}"; do
    # Remove leading ./ from directory name if present
    dir=${dir#./}

    echo "Entering directory: $dir"
    cd "$dir" || { echo "Failed to enter $dir"; exit 1; }

    if $COPY; then
        # Call script with files to copy (using --cp to match second script)
        bash ~/scripts/phonons/make_disp_line_arg.sh --cp "${files_to_copy[@]}"
    else
        # Call script without copying files
        bash ~/scripts/phonons/make_disp_line_arg.sh
    fi

    echo "Finished processing $dir"
    echo "----------------------------------------"
    cd ..
done

echo "All directories processed."
