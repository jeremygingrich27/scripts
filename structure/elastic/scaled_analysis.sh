#!/usr/bin/env bash
# scaled_analysis.sh
# Run analysis.sh in every POSCAR_scaled*/ subdirectory of the current directory.
set -uo pipefail   # not -e: keep going if one directory fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYSIS="${SCRIPT_DIR}/analysis.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [--dim 3D|2D]

Runs analysis.sh inside each POSCAR_scaled*/ directory (errors are reported but
do not stop the loop). Extra options are passed through to analysis.sh.

  -h, --help   show this help and exit
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

shopt -s nullglob
dirs=(POSCAR_scaled*/)
(( ${#dirs[@]} > 0 )) || { echo "ERROR: no POSCAR_scaled*/ directories found" >&2; exit 1; }

fail=0
for dir in "${dirs[@]}"; do
    echo "▶️  $dir"
    if ! ( cd "$dir" && bash "$ANALYSIS" "$@" ); then
        echo "❌ Error in $dir" >&2
        ((fail++))
    fi
done
echo "Done. Failed: ${fail}/${#dirs[@]}"
(( fail == 0 ))
