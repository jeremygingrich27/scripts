#!/usr/bin/env bash
# loop_scale_factor_changer.sh
# Apply change_scaling_factors.py (set the POSCAR scale-factor line to X Y Z) in
# every POSCAR_scaled*/ subdirectory of the current directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANGER="${SCRIPT_DIR}/change_scaling_factors.py"

usage() {
    cat <<USAGE
Usage: $(basename "$0") X Y Z

Runs change_scaling_factors.py X Y Z inside every POSCAR_scaled*/ subdirectory.

  -h, --help   show this help and exit
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }
if [[ $# -ne 3 ]]; then usage >&2; exit 1; fi
X="$1"; Y="$2"; Z="$3"

shopt -s nullglob
dirs=(POSCAR_scaled*/)
(( ${#dirs[@]} > 0 )) || { echo "ERROR: no POSCAR_scaled*/ directories found" >&2; exit 1; }

for dir in "${dirs[@]}"; do
    echo "🔍 $dir"
    ( cd "$dir" && python3 "$CHANGER" "$X" "$Y" "$Z" )
done
echo "✅ Done."
