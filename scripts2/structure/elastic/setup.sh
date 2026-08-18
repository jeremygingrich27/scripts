#!/usr/bin/env bash
# setup.sh
# Generate elastic strain matrices with vaspkit (option 02 -> 201). Run from the
# elastic/ directory (must contain POSCAR). Uses the vaspkit elastic template at
# ~/input_files/vaspkit/elastic_INPUT.in.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"

TEMPLATE="$HOME/input_files/vaspkit/elastic_INPUT.in"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Generate elastic strain matrices via vaspkit (writes INPUT.in, then runs 02->201).

Options:
      --dim 3D|2D   dimensionality token for the template (default: 3D)
  -h, --help        show this help and exit
USAGE
}

DIM="3D"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dim)     DIM="${2:?--dim needs a value}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

need_cmd vaspkit
need_file POSCAR
need_file "$TEMPLATE" "vaspkit elastic template"

sed -e "s/TYPE/1/" -e "s/DIM/$DIM/" "$TEMPLATE" > ./INPUT.in \
    || die "failed to write INPUT.in from $TEMPLATE"
echo -e "02\n201" | vaspkit
