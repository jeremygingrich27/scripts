#!/usr/bin/env bash
# setup_followup_calcs.sh - Efficient VASP calculation setup
set -euo pipefail

echo "🛠️  VASP Follow-up Calculation Setup"

# Find calculation directories containing POSCAR_* subdirectories
CALC_DIRS=()
for d in */; do
    if [[ -d "$d" ]] && ls "$d"POSCAR_* >/dev/null 2>&1; then
        CALC_DIRS+=("${d%/}")
    fi
done

if [[ ${#CALC_DIRS[@]} -eq 0 ]]; then
    echo "❌ No calculation directories with POSCAR_* found"
    exit 1
fi

# Select source calculation
echo "Available calculations:"
PS3="Select OLD calculation: "
select OLD_CALC in "${CALC_DIRS[@]}"; do
    [[ -n "$OLD_CALC" ]] && break
done

# Get new calculation name
read -rp "New calculation name: " NEW_CALC
if [[ -z "$NEW_CALC" ]]; then
    echo "❌ Name required"
    exit 1
fi

NEW_DIR="${NEW_CALC}_from_${OLD_CALC}"
if [[ -d "$NEW_DIR" ]]; then
    read -rp "⚠️  $NEW_DIR exists. Continue? [y/N]: " yn
    if [[ ! "$yn" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get POSCAR directories
POSCAR_DIRS=($(ls -d "$OLD_CALC"/POSCAR_* 2>/dev/null | xargs -n1 basename))
if [[ ${#POSCAR_DIRS[@]} -eq 0 ]]; then
    echo "❌ No POSCAR_* found in $OLD_CALC"
    exit 1
fi

echo "Found ${#POSCAR_DIRS[@]} POSCAR_* directories"
read -rp "Use all? [Y/n]: " use_all
if [[ "$use_all" =~ ^[Nn]$ ]]; then
    for i in "${!POSCAR_DIRS[@]}"; do
        echo "  [$i] ${POSCAR_DIRS[i]}"
    done
    read -rp "Enter indices (space-separated): " -a indices
    SELECTED_DIRS=()
    for i in "${indices[@]}"; do
        if [[ "$i" =~ ^[0-9]+$ ]] && (( i < ${#POSCAR_DIRS[@]} )); then
            SELECTED_DIRS+=("${POSCAR_DIRS[i]}")
        fi
    done
    POSCAR_DIRS=("${SELECTED_DIRS[@]}")
fi

# Parse INCAR parameters
INCAR_FILE="$OLD_CALC/INCAR"
if [[ ! -f "$INCAR_FILE" ]]; then
    echo "❌ INCAR not found in $OLD_CALC"
    exit 1
fi

declare -A PARAMS
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    
    # Parse parameter = value
    if [[ "$line" =~ ^[[:space:]]*([A-Z_]+)[[:space:]]*=[[:space:]]*(.+)$ ]]; then
        param="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        # Remove inline comments
        value="${value%% #*}"
        # Trim whitespace
        value="${value##*( )}"
        value="${value%%*( )}"
        PARAMS["$param"]="$value"
    fi
done < "$INCAR_FILE"

# Parameter variation setup
VARY_PARAMS=false
declare -A PARAM_RANGES
read -rp "Vary INCAR parameters? [y/N]: " vary_ans
if [[ "$vary_ans" =~ ^[Yy]$ ]]; then
    VARY_PARAMS=true
    PARAM_NAMES=($(printf '%s\n' "${!PARAMS[@]}" | sort))
    
    echo "Available parameters:"
    for i in "${!PARAM_NAMES[@]}"; do
        echo "  [$i] ${PARAM_NAMES[i]} = ${PARAMS[${PARAM_NAMES[i]}]}"
    done
    
    read -rp "Parameter indices to vary (space-separated): " -a param_indices
    for idx in "${param_indices[@]}"; do
        if [[ "$idx" =~ ^[0-9]+$ ]] && (( idx < ${#PARAM_NAMES[@]} )); then
            param="${PARAM_NAMES[idx]}"
            echo "Parameter: $param (current: ${PARAMS[$param]})"
            read -rp "  Start:End:Step: " range
            PARAM_RANGES["$param"]="$range"
        fi
    done
fi

# Generate parameter values
PARAM_SETS=()
if $VARY_PARAMS && [[ ${#PARAM_RANGES[@]} -gt 0 ]]; then
    # Handle single parameter variation
    param_name="${!PARAM_RANGES[@]}"
    IFS=':' read -r start end step <<< "${PARAM_RANGES[$param_name]}"
    
    # Generate values using awk for better compatibility
    mapfile -t values < <(awk -v start="$start" -v end="$end" -v step="$step" '
        BEGIN {
            current = start
            while ((step > 0 && current <= end) || (step < 0 && current >= end)) {
                print current
                current += step
            }
        }')
    
    for val in "${values[@]}"; do
        clean_val="${val//./p}"
        PARAM_SETS+=("${param_name}_${clean_val}:${param_name}=${val}")
    done
else
    PARAM_SETS=("default:")
fi

# Copy options
read -rp "Copy CONTCAR→POSCAR? [y/N]: " copy_contcar
read -rp "Extra files (space-separated): " -a extra_files

# Main copy operation
LOGFILE="$NEW_DIR/copy_log.txt"
mkdir -p "$NEW_DIR"
{
    echo "Copy log: $NEW_DIR ($(date))"
    echo "Source: $OLD_CALC"
    echo "Directories: ${#POSCAR_DIRS[@]}, Parameter sets: ${#PARAM_SETS[@]}"
    echo
} > "$LOGFILE"

for param_set in "${PARAM_SETS[@]}"; do
    IFS=':' read -r dir_name param_mod <<< "$param_set"
    [[ -z "$dir_name" ]] && dir_name="default"
    
    echo "📂 $dir_name"
    echo "📂 $dir_name" >> "$LOGFILE"
    
    for poscar_dir in "${POSCAR_DIRS[@]}"; do
        src="$OLD_CALC/$poscar_dir"
        dest="$NEW_DIR/$dir_name/$poscar_dir"
        mkdir -p "$dest"
        
        echo "  📁 $poscar_dir"
        
        # Copy standard files
        for file in POSCAR POTCAR KPOINTS "${extra_files[@]}"; do
            if [[ -f "$src/$file" ]]; then
                cp "$src/$file" "$dest/"
                echo "    ✓ $file"
            fi
        done
        
        # Copy and modify INCAR
        cp "$INCAR_FILE" "$dest/INCAR"
        if [[ -n "$param_mod" ]]; then
            IFS='=' read -r param_key param_val <<< "$param_mod"
            sed -i "s/^[[:space:]]*${param_key}[[:space:]]*=.*/${param_key} = ${param_val}/" "$dest/INCAR"
            echo "    ✓ INCAR ($param_key = $param_val)"
        fi
        
        # Optional CONTCAR copy
        if [[ "$copy_contcar" =~ ^[Yy]$ ]] && [[ -f "$src/CONTCAR" ]]; then
            cp "$src/CONTCAR" "$dest/POSCAR"
            echo "    ✓ CONTCAR→POSCAR"
        fi
        
        echo "    $poscar_dir → $dest" >> "$LOGFILE"
    done
done

echo "✅ Setup complete. Log: $LOGFILE"
if [[ ${#PARAM_SETS[@]} -gt 1 ]]; then
    echo "📊 Created ${#PARAM_SETS[@]} parameter variations"
fi
