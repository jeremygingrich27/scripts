#!/usr/bin/env bash
# distribute_inputs_to_scaled.sh
# Run this script from within a CALC directory to copy selected files
# into all *PATTERN* subdirectories.
set -euo pipefail

ROOT=$PWD
read -rp "What directories do you want to distribute the input files into? " PATTERN

###############################################################################
# 1. Discover files in current CALC directory (non-recursive)
###############################################################################
mapfile -t FILES < <(find . -maxdepth 1 -type f -printf "%f\n" 2>/dev/null | sort)

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No files found in $ROOT"
  exit 1
fi

echo "Files found in current directory ($ROOT):"
for i in "${!FILES[@]}"; do
  echo "  [$i] ${FILES[i]}"
done

read -rp "Enter numbers of files to copy (space-separated, blank = none): " files_to_copy_input

# Handle empty input
if [[ -z "$files_to_copy_input" ]]; then
  echo "No files selected. Exiting."
  exit 0
fi

# Convert input to array
read -ra files_to_copy_indices <<< "$files_to_copy_input"

# Validate indices
FILES_TO_COPY=()
for idx in "${files_to_copy_indices[@]}"; do
  if ! [[ "$idx" =~ ^[0-9]+$ ]] || (( idx < 0 || idx >= ${#FILES[@]} )); then
    echo "Invalid file index: $idx"
    exit 1
  fi
  FILES_TO_COPY+=("${FILES[idx]}")
done

echo
echo "Selected files to copy: ${FILES_TO_COPY[*]}"
echo

###############################################################################
# 2. Find *PATTERN* directories
###############################################################################
mapfile -t TARGET_DIRS < <(find . -maxdepth 1 -type d -name "*${PATTERN}*" | sort)

if [[ ${#TARGET_DIRS[@]} -eq 0 ]]; then
  echo "No *${PATTERN}* directories found in $ROOT"
  exit 1
fi

echo "Copying selected files to the following directories:"
for d in "${TARGET_DIRS[@]}"; do
  echo "  $d"
done
echo

###############################################################################
# 3. Copy files into each *PATTERN* directory
###############################################################################
for d in "${TARGET_DIRS[@]}"; do
  for file in "${FILES_TO_COPY[@]}"; do
    echo "Copying $file → $d/$file"
    cp -f "$file" "$d/"
  done
done

echo
echo "✅ Files successfully copied to all *${PATTERN}* directories."
