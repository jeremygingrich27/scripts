#!/bin/bash

# Script to find and delete all WAVECAR files in subdirectories

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
