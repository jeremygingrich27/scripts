#!/usr/bin/env bash
# setup_followup_calcs.sh - Enhanced VASP calculation setup with improved parameter handling
set -euo pipefail

echo "🛠️   VASP Follow-up Calculation Setup"

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

# Enhanced parameter detection function
detect_param_type() {
    local value="$1"
    
    # Boolean (T/F or .TRUE./.FALSE.)
    if [[ "$value" =~ ^(T|F|\.TRUE\.|\.FALSE\.)$ ]]; then
        echo "boolean"
    # Tuple/Array (space-separated numbers or values)
    elif [[ "$value" =~ ^[0-9.-]+([[:space:]]+[0-9.-]+)+$ ]]; then
        echo "tuple"
    # Float (contains decimal point)
    elif [[ "$value" =~ ^-?[0-9]*\.[0-9]+([eE][+-]?[0-9]+)?$ ]]; then
        echo "float"
    # Integer
    elif [[ "$value" =~ ^-?[0-9]+$ ]]; then
        echo "integer"
    # String (everything else)
    else
        echo "string"
    fi
}

# Generate parameter values based on type and input method
generate_param_values() {
    local param="$1"
    local current_value="$2"
    local param_type
    param_type=$(detect_param_type "$current_value")
    
    echo "Parameter: $param (current: $current_value, type: $param_type)"
    echo "Choose input method:"
    echo "  [1] Specify exact values"
    echo "  [2] Use range (start:end:step) - for numeric types only"
    
    read -rp "Input method [1/2]: " method
    
    local values=()
    case "$method" in
        1)
            echo "Enter values separated by spaces."
            case "$param_type" in
                "boolean")
                    echo "Valid values: T F .TRUE. .FALSE."
                    ;;
                "tuple")
                    echo "For tuples, enclose each tuple in quotes: \"1 2 3\" \"4 5 6\""
                    ;;
                "float")
                    echo "Examples: 0.1 0.01 1e-3"
                    ;;
                "integer")
                    echo "Examples: 1 5 10 100"
                    ;;
                "string")
                    echo "For strings with spaces, use quotes: \"string one\" \"string two\""
                    ;;
            esac
            
            read -rp "Values: " input_values
            
            # Parse input handling quoted strings/tuples
            if [[ "$input_values" =~ \" ]]; then
                # Handle quoted values
                while IFS= read -r -d '' value; do
                    values+=("$value")
                done < <(echo "$input_values" | grep -oP '("[^"]*"|\S+)' | sed 's/"//g' | tr '\n' '\0')
            else
                # Simple space-separated values
                read -ra values <<< "$input_values"
            fi
            ;;
        2)
            if [[ "$param_type" != "integer" && "$param_type" != "float" ]]; then
                echo "❌ Range method only available for numeric types"
                return 1
            fi
            
            read -rp "Range (start:end:step): " range
            IFS=':' read -r start end step <<< "$range"
            
            # Validate numeric inputs
            if ! [[ "$start" =~ ^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$ ]] || \
               ! [[ "$end" =~ ^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$ ]] || \
               ! [[ "$step" =~ ^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$ ]]; then
                echo "❌ Invalid numeric range"
                return 1
            fi
            
            # Generate values using awk
            mapfile -t values < <(awk -v start="$start" -v end="$end" -v step="$step" '
                BEGIN {
                    current = start
                    while ((step > 0 && current <= end) || (step < 0 && current >= end)) {
                        if (current == int(current)) {
                            printf "%.0f\n", current
                        } else {
                            printf "%.6g\n", current
                        }
                        current += step
                    }
                }')
            ;;
        *)
            echo "❌ Invalid input method"
            return 1
            ;;
    esac
    
    # Validate values based on type
    for value in "${values[@]}"; do
        case "$param_type" in
            "boolean")
                if ! [[ "$value" =~ ^(T|F|\.TRUE\.|\.FALSE\.)$ ]]; then
                    echo "❌ Invalid boolean value: $value"
                    return 1
                fi
                ;;
            "integer")
                if ! [[ "$value" =~ ^-?[0-9]+$ ]]; then
                    echo "❌ Invalid integer value: $value"
                    return 1
                fi
                ;;
            "float")
                if ! [[ "$value" =~ ^-?[0-9]*\.?[0-9]+([eE][+-]?[0-9]+)?$ ]]; then
                    echo "❌ Invalid float value: $value"
                    return 1
                fi
                ;;
        esac
    done
    
    # Return values array (using global variable for bash compatibility)
    GENERATED_VALUES=("${values[@]}")
    return 0
}

# Create safe directory name from parameter value
safe_dirname() {
    local value="$1"
    # Replace problematic characters
    value="${value// /_}"           # spaces to underscores
    value="${value//./p}"           # dots to 'p'
    value="${value//-/m}"           # minus to 'm'
    value="${value//+/plus}"        # plus to 'plus'
    value="${value//\"/}"           # remove quotes
    value="${value//\'/}"           # remove single quotes
    echo "$value"
}

# Parameter variation setup
VARY_PARAMS=false
declare -A PARAM_VALUES
read -rp "Vary INCAR parameters? [y/N]: " vary_ans
if [[ "$vary_ans" =~ ^[Yy]$ ]]; then
    VARY_PARAMS=true
    PARAM_NAMES=($(printf '%s\n' "${!PARAMS[@]}" | sort))

    echo "Available parameters:"
    for i in "${!PARAM_NAMES[@]}"; do
        param_type=$(detect_param_type "${PARAMS[${PARAM_NAMES[i]}]}")
        echo "  [$i] ${PARAM_NAMES[i]} = ${PARAMS[${PARAM_NAMES[i]}]} ($param_type)"
    done

    read -rp "Parameter indices to vary (space-separated): " -a param_indices
    for idx in "${param_indices[@]}"; do
        if [[ "$idx" =~ ^[0-9]+$ ]] && (( idx < ${#PARAM_NAMES[@]} )); then
            param="${PARAM_NAMES[idx]}"
            echo
            if generate_param_values "$param" "${PARAMS[$param]}"; then
                PARAM_VALUES["$param"]="${GENERATED_VALUES[*]}"
                echo "✅ Will vary $param with ${#GENERATED_VALUES[@]} values"
            else
                echo "❌ Failed to generate values for $param"
            fi
        fi
    done
fi

# Generate parameter combinations
PARAM_SETS=()
if $VARY_PARAMS && [[ ${#PARAM_VALUES[@]} -gt 0 ]]; then
    if [[ ${#PARAM_VALUES[@]} -eq 1 ]]; then
        # Single parameter variation
        param_name="${!PARAM_VALUES[@]}"
        read -ra param_vals <<< "${PARAM_VALUES[$param_name]}"
        
        for val in "${param_vals[@]}"; do
            safe_val=$(safe_dirname "$val")
            PARAM_SETS+=("${param_name}_${safe_val}:${param_name}=${val}")
        done
    else
        # Multiple parameter variation - Cartesian product
        echo "⚠️  Multiple parameter variation creates Cartesian product"
        echo "This will create many combinations. Continue? [y/N]"
        read -rp "" multi_confirm
        if [[ "$multi_confirm" =~ ^[Yy]$ ]]; then
            # For simplicity, implement basic 2-parameter case
            # Full N-dimensional Cartesian product would need recursive implementation
            param_names=(${!PARAM_VALUES[@]})
            if [[ ${#param_names[@]} -eq 2 ]]; then
                read -ra vals1 <<< "${PARAM_VALUES[${param_names[0]}]}"
                read -ra vals2 <<< "${PARAM_VALUES[${param_names[1]}]}"
                
                for val1 in "${vals1[@]}"; do
                    for val2 in "${vals2[@]}"; do
                        safe_val1=$(safe_dirname "$val1")
                        safe_val2=$(safe_dirname "$val2")
                        dir_name="${param_names[0]}_${safe_val1}_${param_names[1]}_${safe_val2}"
                        param_mods="${param_names[0]}=${val1}|${param_names[1]}=${val2}"
                        PARAM_SETS+=("${dir_name}:${param_mods}")
                    done
                done
            else
                echo "❌ Currently supports up to 2 parameters simultaneously"
                PARAM_SETS=("default:")
            fi
        else
            PARAM_SETS=("default:")
        fi
    fi
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
    IFS=':' read -r dir_name param_mods <<< "$param_set"
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
        if [[ -n "$param_mods" ]]; then
            # Handle multiple parameter modifications
            IFS='|' read -ra modifications <<< "$param_mods"
            for mod in "${modifications[@]}"; do
                IFS='=' read -r param_key param_val <<< "$mod"
                sed -i "s/^[[:space:]]*${param_key}[[:space:]]*=.*/${param_key} = ${param_val}/" "$dest/INCAR"
                echo "    ✓ INCAR ($param_key = $param_val)"
            done
        else
            echo "    ✓ INCAR (no modifications)"
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
