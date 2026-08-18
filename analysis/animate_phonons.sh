#!/bin/bash
# animate_phonons.sh — Generate Phonon Animation Files and View with V_Sim
#
# Prerequisites
# -------------
#   - bash 4+  (for lowercase conversion via ${var,,})
#   - phonopy  (provides the 'phonopy-load' command)
#   - v_sim    (crystal structure visualiser)
#
# Required input file: HIGH_SYMMETRY_POINTS
# -----------------------------------------
# The file must exist in the current directory.  Each data line has the form:
#
#   x_frac  y_frac  z_frac  LABEL
#
# where x, y, z are fractional reciprocal-space coordinates and LABEL is an
# alphanumeric name (e.g. Gamma, X, M, R).  Lines that do not match this
# pattern (comments, blank lines) are ignored.
#
# Example HIGH_SYMMETRY_POINTS:
#   0.000  0.000  0.000  Gamma
#   0.500  0.000  0.000  X
#   0.500  0.500  0.000  M
#   0.500  0.500  0.500  R
#
# Output
# ------
# Animation .ascii files are written to <cwd_basename>_animations/
# A generation log is written to that directory as generation_log.txt.

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
if ! command -v phonopy-load &>/dev/null; then
    echo "Error: 'phonopy-load' not found. Please install phonopy and ensure it is in PATH." >&2
    exit 1
fi

if ! command -v v_sim &>/dev/null; then
    echo "Error: 'v_sim' not found. Please install V_Sim and ensure it is in PATH." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
if [[ ! -f "HIGH_SYMMETRY_POINTS" ]]; then
    echo "Error: HIGH_SYMMETRY_POINTS file not found in $(pwd)." >&2
    echo "Expected format per line:  x_frac  y_frac  z_frac  LABEL" >&2
    exit 1
fi

# Extract valid data lines (numeric x y z followed by a label)
VALID_LINES=($(awk '
    /^[[:space:]]*[0-9.-]+[[:space:]]+[0-9.-]+[[:space:]]+[0-9.-]+[[:space:]]+[A-Za-z0-9_]+/ {
        print $0
    }
' HIGH_SYMMETRY_POINTS))

if [[ ${#VALID_LINES[@]} -eq 0 ]]; then
    echo "Error: No valid high-symmetry point data found in HIGH_SYMMETRY_POINTS." >&2
    exit 1
fi

# Extract the point labels (4th field of each valid line)
OPTIONS=($(awk '
    /^[[:space:]]*[0-9.-]+[[:space:]]+[0-9.-]+[[:space:]]+[0-9.-]+[[:space:]]+[A-Za-z0-9_]+/ {
        print $4
    }
' HIGH_SYMMETRY_POINTS))

# Warn about duplicate labels (phonopy-load would overwrite anime.ascii twice)
DUPLICATES=$(printf "%s\n" "${OPTIONS[@]}" | sort | uniq -d)
if [[ -n "$DUPLICATES" ]]; then
    echo "Warning: Duplicate high-symmetry point labels found:"
    echo "$DUPLICATES"
fi

# ---------------------------------------------------------------------------
# Create output directory and log
# ---------------------------------------------------------------------------
BASE_NAME=$(basename "$(pwd)")
OUT_DIR="${BASE_NAME}_animations"
mkdir -p "$OUT_DIR"
LOG_FILE="${OUT_DIR}/generation_log.txt"
echo "Animation generation log — $(date)" > "$LOG_FILE"

# ---------------------------------------------------------------------------
# Function: generate a single .ascii file for one high-symmetry point
# ---------------------------------------------------------------------------
generate_ascii_file() {
    local label="$1"

    # Extract fractional coordinates for this label
    read -r X Y Z <<< "$(awk -v pt="$label" '$4 == pt {print $1, $2, $3; exit}' HIGH_SYMMETRY_POINTS)"

    if [[ -z "$X" ]]; then
        echo "Error: Label '$label' not found in HIGH_SYMMETRY_POINTS." >&2
        return 1
    fi

    # Format coordinates to one decimal place, removing trailing zeros after decimal
    FORMAT_COORDINATES=()
    for val in "$X" "$Y" "$Z"; do
        rounded=$(printf "%.1f" "$val" | sed -E 's/(\.[0-9]*[1-9])0+$/\1/' | sed -E 's/\.0+$/\.0/')
        FORMAT_COORDINATES+=("$rounded")
    done

    # Run phonopy-load to generate anime.ascii
    phonopy-load --anime "${FORMAT_COORDINATES[@]}"
    if [[ $? -ne 0 ]]; then
        echo "Error: phonopy-load failed for point '$label'." >&2
        echo "FAILED: anime_${label}.ascii" >> "$LOG_FILE"
        return 1
    fi

    # Move the generated file to the output directory
    mv anime.ascii "${OUT_DIR}/anime_${label}.ascii"
    echo "Generated: anime_${label}.ascii" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    echo "[OK] Generated: ${OUT_DIR}/anime_${label}.ascii"
}

# ---------------------------------------------------------------------------
# Ask whether to generate all points or just one
# ---------------------------------------------------------------------------
read -rp "Generate .ascii files for all high-symmetry points? (y/n): " GEN_ALL
GEN_ALL=${GEN_ALL,,}

if [[ "$GEN_ALL" == "y" ]]; then
    for pt in "${OPTIONS[@]}"; do
        generate_ascii_file "$pt"
    done
    echo "All .ascii files generated in: $OUT_DIR"

    # Offer to open one for inspection
    read -rp "Would you like to open one of the animations in V_Sim now? (y/n): " VIEW_ONE
    VIEW_ONE=${VIEW_ONE,,}
    if [[ "$VIEW_ONE" == "y" ]]; then
        echo "Select a point to view:"
        select POINT in "${OPTIONS[@]}"; do
            if [[ -n "$POINT" ]]; then
                export GDK_BACKEND=x11
                v_sim "${OUT_DIR}/anime_${POINT}.ascii" || echo "Error: v_sim failed to launch." >&2
                break
            else
                echo "Invalid selection. Try again."
            fi
        done
    else
        echo "Skipping V_Sim preview."
    fi

else
    echo "Select one of the following high-symmetry points:"
    select POINT in "${OPTIONS[@]}"; do
        if [[ -n "$POINT" ]]; then
            break
        else
            echo "Invalid selection. Try again."
        fi
    done

    generate_ascii_file "$POINT"

    read -rp "Open the animation in V_Sim? (y/n): " OPEN_VSIM
    OPEN_VSIM=${OPEN_VSIM,,}
    if [[ "$OPEN_VSIM" == "y" ]]; then
        export GDK_BACKEND=x11
        v_sim "${OUT_DIR}/anime_${POINT}.ascii" || echo "Error: v_sim failed to launch." >&2
    else
        echo "Skipping V_Sim preview."
    fi
fi
