#!/usr/bin/env bash
# collect_elastic_info.sh
# Finds all ELASTIC_INFO files in current directory and subdirectories,
# copies them to a new directory with names that reflect their origin location

set -euo pipefail

#==============================================================================
# CONFIGURATION
#==============================================================================

SOURCE_DIR="${1:-$PWD}"           # Source directory (default: current directory)
TARGET_DIR="${2:-elastic_results}" # Target directory (default: elastic_results)
FILENAME="ELASTIC_INFO"           # File to search for

echo "🔍 Searching for $FILENAME files in: $SOURCE_DIR"
echo "📁 Target directory: $TARGET_DIR"
echo

#==============================================================================
# SETUP AND DISCOVERY
#==============================================================================

# Create target directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Find all ELASTIC_INFO files
mapfile -t elastic_files < <(find "$SOURCE_DIR" -name "$FILENAME" -type f)

if [[ ${#elastic_files[@]} -eq 0 ]]; then
    echo "❌ No $FILENAME files found in $SOURCE_DIR"
    exit 1
fi

echo "Found ${#elastic_files[@]} $FILENAME file(s):"
echo

#==============================================================================
# FILE PROCESSING AND COPYING
#==============================================================================

# Process each file
for file in "${elastic_files[@]}"; do
    # Get the directory containing the file
    dir=$(dirname "$file")
    
    # Remove the source directory prefix to get relative path
    rel_path="${dir#$SOURCE_DIR}"
    rel_path="${rel_path#/}"  # Remove leading slash if present
    
    # Replace path separators with underscores and clean up
    if [[ -n "$rel_path" ]]; then
        # Convert path to filename-safe format
        safe_name=$(echo "$rel_path" | sed 's|/|_|g' | sed 's|__|_|g')
        new_name="${safe_name}_${FILENAME}"
    else
        # File is in root directory
        new_name="root_${FILENAME}"
    fi
    
    # Handle potential duplicate names by adding a counter
    counter=1
    final_name="$new_name"
    while [[ -f "$TARGET_DIR/$final_name" ]]; do
        final_name="${new_name}_${counter}"
        ((counter++))
    done
    
    # Copy the file
    cp "$file" "$TARGET_DIR/$final_name"
    
    echo "✅ $file"
    echo "   → $TARGET_DIR/$final_name"
    echo
done

echo "🎉 Successfully copied ${#elastic_files[@]} $FILENAME files to $TARGET_DIR/"

#==============================================================================
# SUMMARY FILE GENERATION
#==============================================================================

# Create a summary file
summary_file="$TARGET_DIR/copy_summary.txt"
echo "# ELASTIC_INFO Collection Summary" > "$summary_file"
echo "# Generated on: $(date)" >> "$summary_file"
echo "# Source directory: $SOURCE_DIR" >> "$summary_file"
echo "# Target directory: $TARGET_DIR" >> "$summary_file"
echo "# Files found: ${#elastic_files[@]}" >> "$summary_file"
echo "" >> "$summary_file"

for file in "${elastic_files[@]}"; do
    dir=$(dirname "$file")
    rel_path="${dir#$SOURCE_DIR}"
    rel_path="${rel_path#/}"
    
    if [[ -n "$rel_path" ]]; then
        safe_name=$(echo "$rel_path" | sed 's|/|_|g' | sed 's|__|_|g')
        new_name="${safe_name}_${FILENAME}"
    else
        new_name="root_${FILENAME}"
    fi
    
    # Handle duplicates (same logic as above)
    counter=1
    final_name="$new_name"
    while [[ -f "$TARGET_DIR/$final_name" && "$final_name" != "$new_name" ]]; do
        final_name="${new_name}_${counter}"
        ((counter++))
    done
    
    echo "$file -> $final_name" >> "$summary_file"
done

echo "📋 Summary written to: $summary_file"

#==============================================================================
# STABILITY INFORMATION EXTRACTION
#==============================================================================

echo "🔍 Extracting stability information..."
stability_file="STABILITY_INFO"

# Change to target directory to run grep command
cd "$TARGET_DIR"

# Run grep command to extract eigenvalues information from start pattern to end pattern
# First, create a temporary file to process each file individually
temp_file=$(mktemp)
> "$stability_file"  # Clear the output file

for file in *_ELASTIC_INFO; do
    if [[ -f "$file" ]]; then
        echo "################################################################################" >> "$stability_file"
        echo "# FILE: $file" >> "$stability_file"
        echo "################################################################################" >> "$stability_file"
        echo "" >> "$stability_file"
        
        # Extract from "Eigenvalues of the stiffness matrix" to "This Structure" but stop before "Written ELASTIC_TENSOR"
        sed -n '/Eigenvalues of the stiffness matrix (in GPa):/,/This Structure/p' "$file" | \
        sed '/Written ELASTIC_TENSOR File/,$d' >> "$stability_file"
        
        echo "" >> "$stability_file"
        echo "################################################################################" >> "$stability_file"
        echo "" >> "$stability_file"
        echo "" >> "$stability_file"  # Extra blank lines between files
    fi
done

#==============================================================================
# FINAL OUTPUT AND CLEANUP
#==============================================================================

if [[ -s "$stability_file" ]]; then
    echo "✅ Stability information extracted to: $TARGET_DIR/$stability_file"
else
    echo "⚠️  No stability information found in the copied files"
    echo "# No eigenvalues information found in any ELASTIC_INFO files" > "$stability_file"
    echo "# This may indicate the calculations haven't completed or" >> "$stability_file"
    echo "# the files don't contain stability analysis results" >> "$stability_file"
fi

rm -f "$temp_file"  # Clean up temp file

cd - > /dev/null  # Return to original directory
