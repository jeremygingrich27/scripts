#!/usr/bin/env bash
# elastic_vaspkit.sh
# Build (and optionally submit) a SLURM job that runs VASP in ALL strain_*/
# directories across ALL top-level directories. Run from the parent directory
# that holds the top-level strain groups (e.g. C11_C12_I/, C44/, ...).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"

JOBSCRIPT="elastic_vasp_jobscript.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes ${JOBSCRIPT} running VASP in every strain_*/ directory found under the
immediate subdirectories of the current directory.

Options:
  -N, --nodes N        nodes        (default: ${VASP_NODES})
  -n, --cores N        cores        (default: ${VASP_CORES})
  -q, --queue NAME     partition    (default: ${VASP_QUEUE})
  -t, --time HH:MM:SS  walltime     (default: ${VASP_TIME})
  -A, --account NAME   allocation   (default: ${VASP_ACCOUNT})
      --submit         submit after writing (asks to confirm unless -y)
  -y, --yes            non-interactive: use defaults/flags, no prompts
  -h, --help           show this help and exit
USAGE
}

NODES="${VASP_NODES}"; CORES="${VASP_CORES}"; QUEUE="${VASP_QUEUE}"
TIME="${VASP_TIME}";   ACCOUNT="${VASP_ACCOUNT}"; SUBMIT=0; INTERACTIVE=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        -N|--nodes)   NODES="${2:?--nodes needs a value}";   shift 2 ;;
        -n|--cores)   CORES="${2:?--cores needs a value}";   shift 2 ;;
        -q|--queue)   QUEUE="${2:?--queue needs a value}";   shift 2 ;;
        -t|--time)    TIME="${2:?--time needs a value}";     shift 2 ;;
        -A|--account) ACCOUNT="${2:?--account needs a value}"; shift 2 ;;
        --submit)     SUBMIT=1; shift ;;
        -y|--yes)     INTERACTIVE=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

# ── Discover all strain_*/ directories under each top-level directory ─────────
mapfile -t STRAIN_DIRS < <(find . -mindepth 2 -maxdepth 2 -type d -name "strain_*" -printf '%P\n' | sort)
(( ${#STRAIN_DIRS[@]} > 0 )) || die "no strain_*/ directories found under the subdirectories of $PWD"

echo "Found ${#STRAIN_DIRS[@]} strain_*/ directories:"
printf '  %s\n' "${STRAIN_DIRS[@]}"
echo

DIRS_LITERAL=$(printf '"%s" ' "${STRAIN_DIRS[@]}")

vasp_slurm_header "elastic_vasp" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > "$JOBSCRIPT"
cat >> "$JOBSCRIPT" <<EOF

ROOT="\$PWD"
DIRS=($DIRS_LITERAL)

for ((i=0; i<\${#DIRS[@]}; i++)); do
  CUR="\${DIRS[i]}"
  echo "▶ Step \$((i+1))/\${#DIRS[@]} : \$CUR"
  cd "\$CUR"
  if [[ -f "COMPLETED" ]]; then
    echo "↪ Already completed - skipping"
    cd "\$ROOT"; continue
  fi
  ibrun ${VASP_BIN}
  rc=\$?
  (( rc != 0 )) && { echo "❌ VASP failed (code \$rc) in \$CUR"; exit \$rc; }
  touch COMPLETED
  cd "\$ROOT"
done

echo "🎉 All strain calculations finished successfully."
EOF

echo "✅ Jobscript written to ./${JOBSCRIPT}"

if (( SUBMIT )); then
    if (( INTERACTIVE )) && ! confirm "Submit ${JOBSCRIPT} now?"; then
        echo "Not submitted. Run: sbatch ${JOBSCRIPT}"
    else
        sbatch "$JOBSCRIPT"
    fi
else
    echo "Submit with: sbatch ${JOBSCRIPT}"
fi
