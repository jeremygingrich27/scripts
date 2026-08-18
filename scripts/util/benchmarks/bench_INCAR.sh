#!/bin/bash

# VASP Convergence Testing Script
# This script automates the creation of subdirectories for testing different values
# of INCAR parameters in VASP calculations. It copies POSCAR, POTCAR, and KPOINTS
# files unchanged, and modifies the INCAR file with the specified parameter values.
#
# Usage: Run this script in a directory containing POSCAR, POTCAR, INCAR, and KPOINTS files.

set -e  # Exit on any error

# Global variables
REQUIRED_FILES=("POSCAR" "POTCAR" "INCAR" "KPOINTS")
WORKING_DIR=$(pwd)
CREATED_DIRS=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print section headers
print_header() {
    local message=$1
    local length=${#message}
    local separator=$(printf '=%.0s' $(seq 1 60))
    
    echo
    echo "$separator"
    echo "$message"
    echo "$separator"
}

# Function to check if required files exist
check_required_files() {
    local missing_files=()
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ ! -f "$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        print_color $RED "Error: Missing required files: ${missing_files[*]}"
        print_color $RED "Please ensure all files (${REQUIRED_FILES[*]}) are present."
        return 1
    fi
    
    print_color $GREEN "✓ All required files found"
    return 0
}

# Function to read user input with prompt
read_input() {
    local prompt=$1
    local var_name=$2
    local input_value
    
    while true; do
        echo -n "$prompt"
        read input_value
        input_value=$(echo "$input_value" | xargs)  # Trim whitespace
        
        if [[ -n "$input_value" ]]; then
            eval "$var_name='$input_value'"
            break
        else
            print_color $YELLOW "Please enter a valid value."
        fi
    done
}

# Function to parse different value input formats
parse_values() {
    local input=$1
    local -n values_array=$2
    values_array=()
    
    # Check for range notation (start:end:step)
    if [[ "$input" =~ ^[0-9.-]+:[0-9.-]+:[0-9.-]+$ ]]; then
        IFS=':' read -ra range_parts <<< "$input"
        local start=${range_parts[0]}
        local end=${range_parts[1]}
        local step=${range_parts[2]}
        
        # Use bc for floating point arithmetic
        local current=$start
        while (( $(echo "$current <= $end" | bc -l) )); do
            # Check if it's a whole number
            if [[ "$current" =~ ^[0-9]+$ ]] || [[ "$current" == *.0 ]]; then
                values_array+=($(echo "$current" | cut -d'.' -f1))
            else
                values_array+=("$current")
            fi
            current=$(echo "$current + $step" | bc -l)
        done
    else
        # Handle comma or space separated values
        if [[ "$input" == *","* ]]; then
            IFS=',' read -ra temp_array <<< "$input"
        else
            IFS=' ' read -ra temp_array <<< "$input"
        fi
        
        for val in "${temp_array[@]}"; do
            val=$(echo "$val" | xargs)  # Trim whitespace
            if [[ -n "$val" ]]; then
                values_array+=("$val")
            fi
        done
    fi
    
    return 0
}

# Function to get user input for tag and values
get_user_input() {
    print_header "VASP Convergence Testing Setup"
    
    # Get the INCAR tag to test
    read_input $'\nEnter the INCAR tag to test (e.g., ENCUT, NCORE, SIGMA): ' TAG
    TAG=$(echo "$TAG" | tr '[:lower:]' '[:upper:]')  # Convert to uppercase
    
    # Instructions for value input
    echo
    print_color $BLUE "Enter the values to test for $TAG."
    print_color $BLUE "You can enter them in several ways:"
    print_color $BLUE "1. Space-separated: 400 450 500 550 600"
    print_color $BLUE "2. Comma-separated: 400, 450, 500, 550, 600"
    print_color $BLUE "3. Range notation: 400:600:50 (start:end:step)"
    
    # Get the values to test
    local values_input
    read_input $'\nValues for '"$TAG"': ' values_input
    
    parse_values "$values_input" VALUES
    
    if [[ ${#VALUES[@]} -eq 0 ]]; then
        print_color $RED "Error: No valid values parsed."
        return 1
    fi
}

# Function to modify INCAR file with new tag value
modify_incar() {
    local original_incar=$1
    local output_incar=$2
    local tag=$3
    local value=$4
    local tag_found=false
    
    # Create header for new INCAR
    {
        echo "# INCAR file for VASP convergence test"
        echo "# Generated automatically - modify original INCAR if needed"
        echo
    } > "$output_incar"
    
    # Process original INCAR line by line
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip empty lines initially - we'll add them back
        if [[ -z "$(echo "$line" | xargs)" ]]; then
            echo >> "$output_incar"
            continue
        fi
        
        # Handle comments
        if [[ "$line" =~ ^[[:space:]]*[#!] ]]; then
            echo "$line" >> "$output_incar"
            continue
        fi
        
        # Check if line contains our tag
        if [[ "$line" =~ ^[[:space:]]*${tag}[[:space:]]*= ]]; then
            echo "$tag = $value" >> "$output_incar"
            tag_found=true
        else
            echo "$line" >> "$output_incar"
        fi
    done < "$original_incar"
    
    # If tag wasn't found, add it at the end
    if [[ "$tag_found" == false ]]; then
        echo "$tag = $value" >> "$output_incar"
    fi
    
    return 0
}

# Function to create test directories
create_test_directories() {
    local tag=$1
    shift
    local values=("$@")
    
    # Create main convergence directory
    local main_dir="${tag}_convergence_test"
    local main_path="$WORKING_DIR/$main_dir"
    
    print_color $BLUE "\nCreating main directory: $main_dir"
    if ! mkdir -p "$main_path"; then
        print_color $RED "✗ Error creating main directory $main_dir"
        return 1
    fi
    print_color $GREEN "✓ Created main directory: $main_dir/"
    
    print_color $BLUE "\nCreating test subdirectories for $tag..."
    echo "----------------------------------------"
    
    for value in "${values[@]}"; do
        local dir_name="${tag}_${value}"
        local dir_path="$main_path/$dir_name"
        
        # Create directory
        if mkdir -p "$dir_path"; then
            # Copy POSCAR, POTCAR, and KPOINTS unchanged
            local success=true
            for file in "POSCAR" "POTCAR" "KPOINTS"; do
                if ! cp "$file" "$dir_path/"; then
                    print_color $RED "✗ Failed to copy $file to $dir_name/"
                    success=false
                    break
                fi
            done
            
            # Modify and copy INCAR
            if [[ "$success" == true ]]; then
                if modify_incar "INCAR" "$dir_path/INCAR" "$tag" "$value"; then
                    CREATED_DIRS+=("$main_dir/$dir_name")
                    print_color $GREEN "✓ Created $main_dir/$dir_name/ with $tag = $value"
                else
                    print_color $RED "✗ Failed to create INCAR in $main_dir/$dir_name/"
                fi
            fi
        else
            print_color $RED "✗ Error creating directory $main_dir/$dir_name"
        fi
    done
}

# Function to print summary
print_summary() {
    local tag=$1
    shift
    local values=("$@")
    
    print_header "SUMMARY"
    echo "Tag tested: $tag"
    echo "Values: ${values[*]}"
    echo "Directories created: ${#CREATED_DIRS[@]}"
    
    if [[ ${#CREATED_DIRS[@]} -gt 0 ]]; then
        echo
        print_color $GREEN "Created directories:"
        for dir_name in "${CREATED_DIRS[@]}"; do
            echo "  - $dir_name/"
        done
        
        echo
        print_color $BLUE "Next steps:"
        print_color $BLUE "1. Navigate to each directory and run VASP"
        print_color $BLUE "2. Collect and analyze results for convergence"
        print_color $BLUE "3. Example: cd ${CREATED_DIRS[0]} && mpirun -np <cores> vasp_std"
    else
        print_color $RED "\nNo directories were created successfully."
    fi
}

# Function to confirm with user
confirm_operation() {
    local tag=$1
    shift
    local values=("$@")
    
    echo
    print_color $YELLOW "You want to test $tag with values: ${values[*]}"
    echo -n "Proceed? (y/n): "
    read -r confirm
    
    case "$confirm" in
        [yY]|[yY][eE][sS])
            return 0
            ;;
        *)
            print_color $YELLOW "Operation cancelled."
            return 1
            ;;
    esac
}

# Main function
main() {
    echo "VASP Convergence Testing Script"
    echo "Working directory: $WORKING_DIR"
    
    # Check for required files
    if ! check_required_files; then
        exit 1
    fi
    
    # Get user input
    if ! get_user_input; then
        exit 1
    fi
    
    # Confirm with user
    if ! confirm_operation "$TAG" "${VALUES[@]}"; then
        exit 1
    fi
    
    # Create test directories
    create_test_directories "$TAG" "${VALUES[@]}"
    
    # Print summary
    print_summary "$TAG" "${VALUES[@]}"
    
    # Exit with appropriate code
    if [[ ${#CREATED_DIRS[@]} -gt 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Check if bc is available (needed for range calculations)
if ! command -v bc &> /dev/null; then
    print_color $RED "Error: 'bc' calculator is required but not installed."
    print_color $RED "Please install bc: sudo apt-get install bc (Ubuntu/Debian) or yum install bc (RHEL/CentOS)"
    exit 1
fi

# Run main function
main "$@"
