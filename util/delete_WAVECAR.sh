#!/usr/bin/env bash
# delete_WAVECAR.sh — find all WAVECAR files below the current dir and, after
# showing their total size, delete them on confirmation.
set -uo pipefail

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && {
    echo "Usage: $(basename "$0")   (lists WAVECAR files and total size, then deletes on y/N)"
    exit 0
}

echo "Searching for WAVECAR files..."
echo "================================"

# Find all WAVECAR files
wavecar_files=$(find . -name "WAVECAR" -type f)

if [ -z "$wavecar_files" ]; then
    echo "No WAVECAR files found."
    exit 0
fi

# Count and display files
count=$(echo "$wavecar_files" | wc -l)
echo "Found $count WAVECAR file(s):"
echo "$wavecar_files"
echo ""

# Calculate total size
total_size=$(find . -name "WAVECAR" -type f -exec du -ch {} + | tail -1 | cut -f1)
echo "Total size: $total_size"
echo ""

# Ask for confirmation
read -p "Do you want to delete all these WAVECAR files? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Deleting WAVECAR files..."
    find . -name "WAVECAR" -type f -delete
    echo "✅ All WAVECAR files have been deleted."
else
    echo "❌ Operation cancelled."
fi
