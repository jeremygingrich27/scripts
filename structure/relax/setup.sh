#!/usr/bin/env bash
# setup.sh
# Create a relax/ directory from a folder of VASP inputs, installing a
# relaxation INCAR. Run from the directory that holds the input folder and the
# relaxation INCAR file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options] <input_dir>

Copies <input_dir> to ./<name> and installs the relaxation INCAR.

Options:
      --incar FILE   relaxation INCAR to install as <name>/INCAR (default: relax_INCAR)
      --name DIR     name of the directory to create               (default: relax)
  -f, --force        overwrite the target directory if it exists
  -h, --help         show this help and exit

Example:
  $(basename "$0") input_files/
  $(basename "$0") --incar scf_INCAR --name relax2 input_files/
USAGE
}

INCAR_FILE="relax_INCAR"
TARGET="relax"
FORCE=0
INPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --incar)    INCAR_FILE="${2:?--incar needs a value}"; shift 2 ;;
        --name)     TARGET="${2:?--name needs a value}";      shift 2 ;;
        -f|--force) FORCE=1; shift ;;
        -h|--help)  usage; exit 0 ;;
        -*) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
        *)  [[ -z "$INPUT_DIR" ]] || die "only one input directory may be given"
            INPUT_DIR="$1"; shift ;;
    esac
done

[[ -n "$INPUT_DIR" ]] || { usage >&2; die "an input directory is required"; }
INPUT_DIR="${INPUT_DIR%/}"

[[ -d "$INPUT_DIR" ]] || die "input directory not found: $INPUT_DIR"
for f in POSCAR POTCAR KPOINTS; do
    need_file "$INPUT_DIR/$f" "$INPUT_DIR/$f"
done
need_file "$INCAR_FILE" "relaxation INCAR ($INCAR_FILE)"

if [[ -e "$TARGET" ]]; then
    if (( FORCE )); then
        rm -rf "$TARGET"
    else
        die "'$TARGET' already exists (use -f/--force to overwrite)"
    fi
fi

cp -r "$INPUT_DIR" "$TARGET"
cp "$INCAR_FILE" "$TARGET/INCAR"
echo "✅ Created '$TARGET/' from '$INPUT_DIR' with INCAR '$INCAR_FILE'."
