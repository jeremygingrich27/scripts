#!/usr/bin/env bash
# basic_loop_cmd.sh — TEMPLATE. Loops over every subdirectory; add your own
# commands in the marked section, then run it. (Edit before use.)
set -uo pipefail

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && {
    echo "Usage: $(basename "$0")   (template: edit the marked section to add commands, then run)"
    exit 0
}

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

