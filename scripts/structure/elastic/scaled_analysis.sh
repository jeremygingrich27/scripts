#!/bin/bash

# Loop through matching directories
for dir in POSCAR_scaled*/; do
    if [ -d "$dir" ]; then
        echo "▶️ Running analysis in: $dir"
        (cd "$dir" && bash ~/scripts/structure/elastic/analysis.sh)
        if [ $? -ne 0 ]; then
            echo "❌ Error in $dir"
        fi
    fi
done

