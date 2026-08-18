#!/usr/bin/env bash
# fd_phonons_job.sh
# Generate (and by default submit) a SLURM job that runs VASP in every
# displacement subdirectory, then collects force constants with phonopy -f.
# Run from inside the phonons/ directory containing the displacement subdirs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"

JOBSCRIPT="phonons_vasp_jobscript.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes ${JOBSCRIPT} (VASP in each displacement dir, then phonopy -f) and submits it.

Options:
  -n, --nodes N        nodes        (default: ${VASP_NODES})
  -c, --cores N        cores        (default: ${VASP_CORES})
  -q, --queue NAME     partition    (default: ${VASP_QUEUE})
  -t, --time HH:MM:SS  walltime     (default: ${VASP_TIME})
  -a, --account NAME   allocation   (default: ${VASP_ACCOUNT})
      --no-submit      write the jobscript but do not submit it
  -h, --help           show this help and exit
USAGE
}

NODES="${VASP_NODES}"; CORES="${VASP_CORES}"; QUEUE="${VASP_QUEUE}"
TIME="${VASP_TIME}";   ACCOUNT="${VASP_ACCOUNT}"; SUBMIT=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--nodes)   NODES="${2:?--nodes needs a value}";   shift 2 ;;
        -c|--cores)   CORES="${2:?--cores needs a value}";   shift 2 ;;
        -q|--queue)   QUEUE="${2:?--queue needs a value}";   shift 2 ;;
        -t|--time)    TIME="${2:?--time needs a value}";     shift 2 ;;
        -a|--account) ACCOUNT="${2:?--account needs a value}"; shift 2 ;;
        --no-submit)  SUBMIT=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

mapfile -t DIRS < <(find . -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
(( ${#DIRS[@]} > 0 )) || die "no displacement subdirectories found in $PWD"
echo "Found ${#DIRS[@]} subdirectories:"; printf '  %s\n' "${DIRS[@]}"; echo

DIRS_LITERAL=$(printf '"%s" ' "${DIRS[@]}")

vasp_slurm_header "phonons_vasp" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > "$JOBSCRIPT"
cat >> "$JOBSCRIPT" <<EOF

ROOT="\$PWD"
DIRS=($DIRS_LITERAL)

for DIR in "\${DIRS[@]}"; do
    echo "Running VASP in \$DIR"
    cd "\$DIR"
    if [[ -f COMPLETED ]]; then
        echo "  Already completed – skipping"; cd "\$ROOT"; continue
    fi
    ibrun ${VASP_BIN} || exit \$?
    touch COMPLETED
    cd "\$ROOT"
done

echo "Collecting force constants with phonopy..."
PHONOPY_FILES=()
for DIR in "\${DIRS[@]}"; do
    if [[ -f "\$DIR/vasprun.xml" ]]; then
        PHONOPY_FILES+=("\$DIR/vasprun.xml")
    else
        echo "Warning: vasprun.xml not found in \$DIR"
    fi
done

if (( \${#PHONOPY_FILES[@]} > 0 )); then
    phonopy -f "\${PHONOPY_FILES[@]}"
    echo "Phonopy completed successfully."
else
    echo "No vasprun.xml files found – phonopy skipped."; exit 1
fi
echo "All calculations finished successfully."
EOF

echo "✅ Jobscript written to ./${JOBSCRIPT}"
if (( SUBMIT )); then
    echo "Submitting: nodes=$NODES cores=$CORES queue=$QUEUE time=$TIME"
    sbatch "$JOBSCRIPT"
    echo "Monitor with: squeue -u \$USER"
else
    echo "Submit with: sbatch ${JOBSCRIPT}"
fi
