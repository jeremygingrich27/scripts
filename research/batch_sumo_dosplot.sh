#!/bin/bash
# batch_sumo_dosplot.sh — Batch DOS Plotting with sumo-dosplot
#
# Interactively builds a sumo-dosplot command from up to 32 configurable
# parameters, then runs it in every selected subdirectory that contains the
# target input file (default: vasprun.xml).
#
# Prerequisites
# -------------
#   - sumo  (https://github.com/SMTG-Bham/sumo)
#             Install:  pip install sumo
#   - A VASP vasprun.xml in each directory to process, *or* a Questaal
#     opt.ext file if using --code questaal.
#
# Usage
# -----
#   1. Run the script from any parent directory:
#
#        bash batch_sumo_dosplot.sh
#
#   2. A numbered list of the 32 available options is shown.  Enter the
#      indices of options you want to set (comma-separated), or 'all':
#
#        Enter the indices of options you want to specify: 0,4,20,21,29
#
#   3. For each chosen option, enter a value (or press Enter for the default).
#
#   4. The script searches recursively for subdirectories containing the
#      target input file and shows them numbered.  Enter indices, a range
#      (e.g. 2-5), or 'all'.
#
#   5. sumo-dosplot is executed in each selected directory.
#
# Quick examples
# --------------
#   * Plot only total DOS, energy window -4 to 4 eV, save as PNG at 300 DPI:
#       Indices: 16,20,21,29,30
#       Values:  true | -4.0 | 4.0 | png | 300
#
#   * Plot Ti.d and O.p projected DOS with gaussian broadening 0.05:
#       Indices: 4,9
#       Values:  Ti.d,O.p | 0.05
#
# Configurable parameters (indices 0-31)
# ---------------------------------------
#   0   -f / --filename       vasprun.xml file to plot          (default: vasprun.xml)
#   1   -c / --code           Input format: vasp or questaal    (default: vasp)
#   2   -p / --prefix         Prefix for generated files        (default: cwd name)
#   3   -d / --directory      Output directory                  (default: none)
#   4   -e / --elements       Elemental orbitals, e.g. C.s.p,O (default: none)
#   5   -o / --orbitals       lm-decomposed orbitals, e.g. Ru.d(default: none)
#   6   -a / --atoms          Atoms to include, e.g. O.1.2.3   (default: none)
#   7       --spin            Spin channel: up/1 or down/-1     (default: none)
#   8   -s / --subplot        Separate subplots per element     (default: false)
#   9   -g / --gaussian       Gaussian broadening std dev       (default: none)
#   10      --columns         Legend columns                    (default: 2)
#   11      --legend-cutoff   Label cutoff (% of total DOS)     (default: 3)
#   12      --no-legend       Hide legend                       (default: true)
#   13      --legend-frame    Box around legend                 (default: false)
#   14      --no-shift        Do not shift VBM/Fermi to 0 eV   (default: true)
#   15      --zero-energy     Reference energy shifted to zero  (default: none)
#   16      --total-only      Plot total DOS only               (default: false)
#   17      --no-total        Omit total DOS                    (default: true)
#   18      --height          Graph height (inches)             (default: none)
#   19      --width           Graph width (inches)              (default: none)
#   20      --xmin            Minimum energy on x-axis          (default: -6.0)
#   21      --xmax            Maximum energy on x-axis          (default:  6.0)
#   22      --config          Colour configuration file         (default: none)
#   23      --style           Matplotlib style specification    (default: none)
#   24      --no-base-style   Disable sumo base style           (default: false)
#   25      --xlabel          x-axis label/units                (default: 'Energy (eV)')
#   26      --ylabel          y-axis label/units                (default: 'DOS')
#   27      --yscale          y-axis scaling factor             (default: 1)
#   28      --zero-line       Vertical line at energy zero      (default: false)
#   29      --format          Image format: pdf/svg/jpg/png     (default: pdf)
#   30      --dpi             Pixel density for image file      (default: 400)
#   31      --font            Font to use                       (default: none)
#
# Security note
# -------------
#   This script uses 'eval' to execute the assembled sumo-dosplot command.
#   eval is necessary here because sumo-dosplot arguments contain quoted
#   strings with spaces (e.g. axis labels).  As a result, user-supplied
#   input is interpreted by the shell.  Run this script only in trusted
#   environments with trusted input values.

# Function to display all options
show_options() {
    echo "Available options:"
    echo " 0: -f, --filename       vasprun.xml file to plot (default: vasprun.xml)"
    echo " 1: -c, --code           Input file format: 'vasp' (vasprun.xml) or 'questaal' (opt.ext) (default: vasp)"
    echo " 2: -p, --prefix         prefix for the files generated (default: none)"
    echo " 3: -d, --directory      output directory for files (default: none)"
    echo " 4: -e, --elements       elemental orbitals to plot (e.g. 'C.s.p,O') (default: none)"
    echo " 5: -o, --orbitals       orbitals to split into lm-decomposed contributions (e.g. 'Ru.d') (default: none)"
    echo " 6: -a, --atoms          atoms to include (e.g. 'O.1.2.3,Ru.1.2.3') (default: none)"
    echo " 7: --spin               select one spin channel only (options: up, 1; down, -1) (default: none)"
    echo " 8: -s, --subplot        plot each element on separate subplots (default: false)"
    echo " 9: -g, --gaussian       standard deviation of gaussian broadening (default: none)"
    echo "10: --columns            number of columns in the legend (default: 2)"
    echo "11: --legend-cutoff      cut-off in % of total DOS for label (default: 3)"
    echo "12: --no-legend          hide the plot legend (default: true)"
    echo "13: --legend-frame       display a box around the legend (default: false)"
    echo "14: --no-shift           don't shift the VBM/Fermi level to 0 eV (default: true)"
    echo "15: --zero-energy        Reference energy to shift to zero (default: none)"
    echo "16: --total-only         only plot the total density of states (default: false)"
    echo "17: --no-total           don't plot the total density of states (default: true)"
    echo "18: --height             height of the graph (default: none)"
    echo "19: --width              width of the graph (default: none)"
    echo "20: --xmin               minimum energy on the x-axis (default: -6.0)"
    echo "21: --xmax               maximum energy on the x-axis (default: 6.0)"
    echo "22: --config             colour configuration file (default: none)"
    echo "23: --style              matplotlib style specifications (default: none)"
    echo "24: --no-base-style      prevent use of sumo base style (default: false)"
    echo "25: --xlabel             x-axis (i.e. energy) label/units (default: 'Energy (eV)')"
    echo "26: --ylabel             y-axis (i.e. DOS) label/units (default: 'DOS')"
    echo "27: --yscale             scaling factor for the y-axis (default: 1)"
    echo "28: --zero-line          Plot vertical line at energy zero (default: false)"
    echo "29: --format             image file format (options: pdf, svg, jpg, png) (default: pdf)"
    echo "30: --dpi                pixel density for image file (default: 400)"
    echo "31: --font               font to use (default: none)"
}

# Function to get user input with default
get_input() {
    local prompt="$1"
    local default="$2"
    read -p "$prompt (default: $default): " value
    echo "${value:-$default}"
}

# Main script
show_options

# Get which options to configure
read -p "Enter the indices of options you want to specify (comma-separated, or 'all'): " option_indices

# Initialize command
command="sumo-dosplot"

# Process selected options
if [[ "$option_indices" == "all" ]]; then
    option_indices=$(seq 0 31 | tr '\n' ',' | sed 's/,$//')
fi

IFS=',' read -ra indices <<< "$option_indices"
for i in "${indices[@]}"; do
    case $i in
        0)  # filename
            value=$(get_input "Enter vasprun.xml filename" "vasprun.xml")
            command+=" -f \"$value\""
            ;;
        1)  # code
            value=$(get_input "Enter input file format (vasp/questaal)" "vasp")
            command+=" -c \"$value\""
            ;;
        2)  # prefix
	    default_prefix=$(basename "$(pwd)")  # current directory name
 	    value=$(get_input "Enter file prefix" "$default_prefix")
  	    [[ -n "$value" ]] && command+=" -p \"$value\""
	    ;;

        3)  # directory
            value=$(get_input "Enter output directory" "")
            [[ -n "$value" ]] && command+=" -d \"$value\""
            ;;
        4)  # elements
            value=$(get_input "Enter elemental orbitals to plot" "")
            [[ -n "$value" ]] && command+=" -e \"$value\""
            ;;
        5)  # orbitals
            value=$(get_input "Enter orbitals to split" "")
            [[ -n "$value" ]] && command+=" -o \"$value\""
            ;;
        6)  # atoms
            value=$(get_input "Enter atoms to include" "")
            [[ -n "$value" ]] && command+=" -a \"$value\""
            ;;
        7)  # spin
            value=$(get_input "Enter spin channel (up/1 or down/-1)" "")
            [[ -n "$value" ]] && command+=" --spin \"$value\""
            ;;
        8)  # subplot
            value=$(get_input "Enable subplots? (true/false)" "false")
            [[ "$value" == "true" ]] && command+=" -s"
            ;;
        9)  # gaussian
            value=$(get_input "Enter gaussian broadening" "")
            [[ -n "$value" ]] && command+=" -g \"$value\""
            ;;
        10) # columns
            value=$(get_input "Enter number of legend columns" "2")
            command+=" --columns \"$value\""
            ;;
        11) # legend-cutoff
            value=$(get_input "Enter legend cutoff percentage" "3")
            command+=" --legend-cutoff \"$value\""
            ;;
        12) # no-legend
            value=$(get_input "Hide legend? (true/false)" "true")
            [[ "$value" == "true" ]] && command+=" --no-legend"
            ;;
        13) # legend-frame
            value=$(get_input "Add legend frame? (true/false)" "false")
            [[ "$value" == "true" ]] && command+=" --legend-frame"
            ;;
        14) # no-shift
            value=$(get_input "Don't shift VBM? (true/false)" "true")
            [[ "$value" == "true" ]] && command+=" --no-shift"
            ;;
        15) # zero-energy
            value=$(get_input "Enter zero energy reference" "")
            [[ -n "$value" ]] && command+=" --zero-energy \"$value\""
            ;;
        16) # total-only
            value=$(get_input "Plot total DOS only? (true/false)" "false")
            [[ "$value" == "true" ]] && command+=" --total-only"
            ;;
        17) # no-total
            value=$(get_input "Don't plot total DOS? (true/false)" "true")
            [[ "$value" == "true" ]] && command+=" --no-total"
            ;;
        18) # height
            value=$(get_input "Enter graph height" "")
            [[ -n "$value" ]] && command+=" --height \"$value\""
            ;;
        19) # width
            value=$(get_input "Enter graph width" "")
            [[ -n "$value" ]] && command+=" --width \"$value\""
            ;;
        20) # xmin
            value=$(get_input "Enter minimum energy" "-6.0")
            command+=" --xmin \"$value\""
            ;;
        21) # xmax
            value=$(get_input "Enter maximum energy" "6.0")
            command+=" --xmax \"$value\""
            ;;
        22) # config
            value=$(get_input "Enter color config file" "")
            [[ -n "$value" ]] && command+=" --config \"$value\""
            ;;
        23) # style
            value=$(get_input "Enter matplotlib style" "")
            [[ -n "$value" ]] && command+=" --style \"$value\""
            ;;
        24) # no-base-style
            value=$(get_input "Disable base style? (true/false)" "false")
            [[ "$value" == "true" ]] && command+=" --no-base-style"
            ;;
        25) # xlabel
            value=$(get_input "Enter x-axis label" "Energy (eV)")
            command+=" --xlabel \"$value\""
            ;;
        26) # ylabel
            value=$(get_input "Enter y-axis label" "DOS")
            command+=" --ylabel \"$value\""
            ;;
        27) # yscale
            value=$(get_input "Enter y-axis scaling factor" "1")
            command+=" --yscale \"$value\""
            ;;
        28) # zero-line
            value=$(get_input "Plot zero line? (true/false)" "false")
            [[ "$value" == "true" ]] && command+=" --zero-line"
            ;;
        29) # format
            value=$(get_input "Enter image format (pdf/svg/jpg/png)" "pdf")
            command+=" --format \"$value\""
            ;;
        30) # dpi
            value=$(get_input "Enter image DPI" "400")
            command+=" --dpi \"$value\""
            ;;
        31) # font
            value=$(get_input "Enter font to use" "")
            [[ -n "$value" ]] && command+=" --font \"$value\""
            ;;
    esac
done

# Set default filename if not specified
if [[ ! "$command" =~ "-f" ]]; then
    filename="vasprun.xml"
    command+=" -f \"$filename\""
else
    # Extract filename from command
    filename=$(echo "$command" | grep -oP -- '-f \K[^ ]+' | tr -d '"')
fi

# Find all subdirectories containing the file
echo -e "\nSearching for directories containing $filename..."
subdirs=()
while IFS= read -r -d $'\0' dir; do
    subdirs+=("$dir")
done < <(find . -type f -name "$filename" -exec dirname {} \; -print0 | sort -zu)

if [ ${#subdirs[@]} -eq 0 ]; then
    echo "No subdirectories found containing $filename"
    exit 1
fi

# Display found directories
echo -e "\nFound ${#subdirs[@]} directories:"
for i in "${!subdirs[@]}"; do
    echo "$i: ${subdirs[$i]}"
done

# Get directory selection
read -p "Enter which directories to process (comma-separated, range, or 'all'): " dir_selection

# Process selection
selected_dirs=()
if [[ "$dir_selection" == "all" ]]; then
    selected_dirs=("${subdirs[@]}")
else
    # Handle ranges (1-5) and individual numbers
    IFS=',' read -ra parts <<< "$dir_selection"
    for part in "${parts[@]}"; do
        if [[ "$part" =~ ^([0-9]+)-([0-9]+)$ ]]; then
            start=${BASH_REMATCH[1]}
            end=${BASH_REMATCH[2]}
            for ((i=start; i<=end; i++)); do
                selected_dirs+=("${subdirs[$i]}")
            done
        elif [[ "$part" =~ ^[0-9]+$ ]]; then
            selected_dirs+=("${subdirs[$part]}")
        fi
    done
fi

# Remove duplicates
selected_dirs=($(printf "%s\n" "${selected_dirs[@]}" | sort -u))

if [ ${#selected_dirs[@]} -eq 0 ]; then
    echo "No directories selected. Exiting."
    exit 1
fi

# Execute command in each selected directory
echo -e "\nExecuting command in selected directories..."
for dir in "${selected_dirs[@]}"; do
    echo -e "\nProcessing $dir"
    (
        cd "$dir" || exit
        echo "Running: $command"
        eval "$command"
        if [ $? -eq 0 ]; then
            echo "Successfully processed $dir"
        else
            echo "Error processing $dir"
        fi
    )
done

echo -e "\nAll done!"
