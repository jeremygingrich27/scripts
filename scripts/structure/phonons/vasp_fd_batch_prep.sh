#!/bin/bash

# Loop over all directories matching * (add to this for more specificity)
for dir in POSCAR*/; do
    # Check if it's a directory
    if [ -d "$dir" ]; then
        echo "🔍 Entering directory: $dir"
        cd "$dir" || continue

	echo -e "303" | vaspkit
	mv KPATH.in QPOINTS
         
        echo "✅ Finished with $dir"
        cd ..  # Go back to the parent directory
    fi
done

