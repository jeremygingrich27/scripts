#!/usr/bin/env bash
# analysis.sh
# Analyze the elastic tensor with vaspkit (option 02 -> 201) and write
# ELASTIC_INFO. Run from within a completed strain calculation directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"

TEMPLATE="$HOME/input_files/vaspkit/elastic_INPUT.in"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Run vaspkit elastic analysis and write ELASTIC_INFO in the current directory.

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
need_file "$TEMPLATE" "vaspkit elastic template"

sed -e "s/TYPE/2/" -e "s/DIM/$DIM/" "$TEMPLATE" > ./INPUT.in \
    || die "failed to write INPUT.in from $TEMPLATE"

if ! echo -e "02\n201" | vaspkit | awk '/Summary/,0' > ELASTIC_INFO.tmp; then
    die "failed to analyze elastic tensor"
fi

sed -e "s/meeted/met/" ELASTIC_INFO.tmp > ELASTIC_INFO   # fix a vaspkit typo
rm -f ELASTIC_INFO.tmp
echo "✅ Wrote ELASTIC_INFO"
