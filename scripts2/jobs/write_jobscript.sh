#!/usr/bin/env bash
# write_jobscript.sh
# Generate a SLURM jobscript for a VASP run. Works two ways:
#   * interactively  — run with no flags and answer the prompts
#   * non-interactively — pass flags (handy inside other scripts / batch loops)
# Cluster defaults come from ../lib/slurm_defaults.sh (one place to edit them).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"

ADDITIONS_DIR="${SCRIPT_DIR}/additional_functions"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes ./jobscript for a VASP calculation. With no options it runs
interactively; any value can instead be supplied as a flag.

Options:
  -j, --name NAME       job name                     (default: test)
  -N, --nodes N         number of nodes              (default: ${VASP_NODES})
  -n, --cores N         number of cores              (default: ${VASP_CORES})
  -q, --queue NAME      SLURM partition              (default: ${VASP_QUEUE})
  -t, --time HH:MM:SS   walltime                     (default: ${VASP_TIME})
  -A, --account NAME    SLURM allocation             (default: ${VASP_ACCOUNT})
  -d, --dir DIR         VASP input directory to target (for snippet paths)
      --add LIST        snippet(s) from additional_functions/ to append,
                        by name or number, e.g. --add "1 3" or --add relax
  -y, --yes             non-interactive: use defaults/flags, no prompts
  -h, --help            show this help and exit

Examples:
  $(basename "$0")                          # fully interactive
  $(basename "$0") -j relax -t 24:00:00     # override a couple of values
  $(basename "$0") -y -j scf --add relax_until_convergence
USAGE
}

# ── Defaults (cluster values come from the sourced lib) ──────────────────────
NAME="test"
NODES="${VASP_NODES}"
CORES="${VASP_CORES}"
QUEUE="${VASP_QUEUE}"
TIME="${VASP_TIME}"
ACCOUNT="${VASP_ACCOUNT}"
SELECTED_DIR=""
ADD_LIST=""
INTERACTIVE=1

# ── Parse flags ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -j|--name)    NAME="${2:?--name needs a value}";    shift 2 ;;
        -N|--nodes)   NODES="${2:?--nodes needs a value}";  shift 2 ;;
        -n|--cores)   CORES="${2:?--cores needs a value}";  shift 2 ;;
        -q|--queue)   QUEUE="${2:?--queue needs a value}";  shift 2 ;;
        -t|--time)    TIME="${2:?--time needs a value}";    shift 2 ;;
        -A|--account) ACCOUNT="${2:?--account needs a value}"; shift 2 ;;
        -d|--dir)     SELECTED_DIR="${2:?--dir needs a value}"; shift 2 ;;
        --add)        ADD_LIST="${2:?--add needs a value}"; shift 2 ;;
        -y|--yes)     INTERACTIVE=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

# ── Helper: scan subdirectories for a full VASP input set ────────────────────
find_vasp_directories() {
    local dirs=() dir
    for dir in */; do
        if [[ -f "$dir/POSCAR" && -f "$dir/POTCAR" && -f "$dir/KPOINTS" ]]; then
            dirs+=("${dir%/}")
        fi
    done
    printf '%s\n' "${dirs[@]}"
}

# ── Interactive: offer to pick a VASP directory, then prompt for SLURM values ─
if (( INTERACTIVE )); then
    if [[ -z "$SELECTED_DIR" ]]; then
        mapfile -t VASP_DIRS < <(find_vasp_directories)
        if (( ${#VASP_DIRS[@]} == 1 )); then
            SELECTED_DIR="${VASP_DIRS[0]}"
            echo "Found one directory with VASP inputs: $SELECTED_DIR"
        elif (( ${#VASP_DIRS[@]} > 1 )); then
            echo "Directories with a full VASP input set:"
            for i in "${!VASP_DIRS[@]}"; do
                printf "  %2d) %s\n" "$((i+1))" "${VASP_DIRS[i]}"
            done
            read -rp "Select a directory (1-${#VASP_DIRS[@]}), or Enter to skip: " choice
            if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice>=1 && choice<=${#VASP_DIRS[@]} )); then
                SELECTED_DIR="${VASP_DIRS[$((choice-1))]}"
            fi
        fi
        [[ -n "$SELECTED_DIR" ]] && echo "Targeting directory: $SELECTED_DIR" && echo
    fi

    read -rp "Enter calc name [${NAME}]: " r;    NAME="${r:-$NAME}"
    read -rp "Enter # of nodes [${NODES}]: " r;  NODES="${r:-$NODES}"
    read -rp "Enter # of cores [${CORES}]: " r;  CORES="${r:-$CORES}"
    read -rp "Enter queue name [${QUEUE}]: " r;  QUEUE="${r:-$QUEUE}"
    read -rp "Enter job length [${TIME}]: " r;   TIME="${r:-$TIME}"
    read -rp "Enter account [${ACCOUNT}]: " r;   ACCOUNT="${r:-$ACCOUNT}"
    echo
fi

# ── Validate ─────────────────────────────────────────────────────────────────
[[ "$NODES" =~ ^[0-9]+$ ]]            || die "nodes must be an integer: $NODES"
[[ "$CORES" =~ ^[0-9]+$ ]]            || die "cores must be an integer: $CORES"
[[ "$TIME"  =~ ^[0-9]+:[0-9]{2}:[0-9]{2}$ ]] || die "walltime must be HH:MM:SS: $TIME"
[[ -z "$SELECTED_DIR" || -d "$SELECTED_DIR" ]] || die "target directory not found: $SELECTED_DIR"

# ── 1. Header (from the shared lib) ──────────────────────────────────────────
vasp_slurm_header "$NAME" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > jobscript
cat >> jobscript <<'EOF'
start_time=$(date +%s)
CURRENT_DIR=$(pwd)
EOF

# ── 2. Optional snippet additions ────────────────────────────────────────────
append_snippet() {
    local file="$1" content
    content="$(cat "$file")"
    [[ -n "$SELECTED_DIR" ]] && content="${content//original_directory/$SELECTED_DIR}"
    {
        printf '\n# ===== Begin %s =====\n' "$(basename "$file")"
        printf '%s\n' "$content"
        printf 'cd "$CURRENT_DIR"\n'
        printf '# ===== End %s =====\n' "$(basename "$file")"
    } >> jobscript
}

if [[ -d "$ADDITIONS_DIR" ]] && compgen -G "$ADDITIONS_DIR"/* >/dev/null; then
    mapfile -t ADDITION_FILES < <(ls -1 "$ADDITIONS_DIR"/*)

    # In interactive mode (and when no --add was given) show the menu.
    if (( INTERACTIVE )) && [[ -z "$ADD_LIST" ]]; then
        echo "Optional jobscript additions in: $ADDITIONS_DIR"
        for i in "${!ADDITION_FILES[@]}"; do
            printf "  %2d) %s\n" "$((i+1))" "$(basename "${ADDITION_FILES[i]}")"
        done
        read -rp "Numbers to append (e.g. 1 3), or Enter for none: " ADD_LIST
        echo
    fi

    for token in ${ADD_LIST//,/ }; do
        file=""
        if [[ "$token" =~ ^[0-9]+$ ]] && (( token>=1 && token<=${#ADDITION_FILES[@]} )); then
            file="${ADDITION_FILES[$((token-1))]}"
        else
            for f in "${ADDITION_FILES[@]}"; do
                [[ "$(basename "$f")" == "$token" ]] && file="$f" && break
            done
        fi
        if [[ -n "$file" ]]; then
            echo ">>> Appending $(basename "$file")"
            append_snippet "$file"
        else
            echo ">>> Skipping unknown addition: '$token'" >&2
        fi
    done
elif [[ -n "$ADD_LIST" ]]; then
    die "no additional_functions/ snippets found in $ADDITIONS_DIR"
fi

# ── 3. Footer ────────────────────────────────────────────────────────────────
cat >> jobscript <<'EOF'
status=$?
end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo "Job completed in $elapsed seconds"
exit $status
EOF

echo "✅ Jobscript written to ./jobscript  (${NODES} node(s), ${CORES} cores, ${QUEUE}, ${TIME})"
