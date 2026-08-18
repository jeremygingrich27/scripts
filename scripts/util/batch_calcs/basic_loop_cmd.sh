#!/bin/bash

# Loop over all directories matching * (add to this for more specificity)
for dir in */; do
    # Check if it's a directory
    if [ -d "$dir" ]; then
        echo "🔍 Entering directory: $dir"
        cd "$dir" || continue

        # ========================
        # Place your commands here
        # Example: echo -e "102\n2\n0.04\n" | vaspkit 
        # 
        # ========================



        # ========================
        echo "✅ Finished with $dir"
        cd ..  # Go back to the parent directory
    fi
done

