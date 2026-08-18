#!/bin/bash

read -p "Name of jobscript to submit: " jobscript

og_dir=$(pwd)

# Loop over all subdirectories
for dir in */; do
    if [ -d "$dir" ]; then
        echo "🔍 Entering directory: $dir"
        cd "$dir" || continue

        sbatch "$jobscript"

        echo "✅ Submitted in $dir"
        cd "$og_dir" || exit
    fi
done

