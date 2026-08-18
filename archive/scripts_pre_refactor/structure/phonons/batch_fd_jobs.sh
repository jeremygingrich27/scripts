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

# Interactive SLURM configuration
read -p "Number of nodes [1]: " NODES
NODES=${NODES:-1}

read -p "Number of cores [128]: " CORES
CORES=${CORES:-128}

read -p "Queue/partition [normal]: " QUEUE
QUEUE=${QUEUE:-normal}

read -p "Walltime [48:00:00]: " TIME
TIME=${TIME:-48:00:00}

read -p "Account name [PHY24018]: " ACCOUNT
ACCOUNT=${ACCOUNT:-PHY24018}

# Build the command arguments
CMD_ARGS=(-n "$NODES" -c "$CORES" -q "$QUEUE" -t "$TIME" -a "$ACCOUNT")

# Loop through each directory
for dir in "${dirs[@]}"; do
    # Remove leading ./ from directory name if present
    dir=${dir#./}

    echo "Entering directory: $dir"
    cd "$dir" || { echo "Failed to enter $dir"; exit 1; }

    echo "Submitting job with parameters:"
    echo "  Nodes: $NODES  Cores: $CORES  Queue: $QUEUE  Time: $TIME  Account: $ACCOUNT"
    bash ~/scripts/structure/phonons/fd_phonons_job_line_arg.sh "${CMD_ARGS[@]}"

    echo "Finished processing $dir"
    echo "----------------------------------------"
    cd ..
done

echo "All directories processed."
