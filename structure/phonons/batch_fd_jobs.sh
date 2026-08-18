#!/usr/bin/env bash
# batch_fd_jobs.sh
# Run fd_phonons_job.sh for every POSCAR*/ subdirectory, prompting once for SLURM
# resources and applying them to all. Run from the directory holding POSCAR*/ dirs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && {
    echo "Usage: $(basename "$0")"
    echo "Prompts once for SLURM resources, then runs fd_phonons_job.sh in each POSCAR*/ dir."
    exit 0
}

mapfile -t dirs < <(find . -maxdepth 1 -type d -name "POSCAR*" -printf '%f\n' | sort)
(( ${#dirs[@]} > 0 )) || { echo "No POSCAR*/ directories found." >&2; exit 1; }

echo "Found ${#dirs[@]} POSCAR* directories:"; printf '  %s\n' "${dirs[@]}"; echo

read -rp "Number of nodes [${VASP_NODES}]: " NODES;     NODES="${NODES:-$VASP_NODES}"
read -rp "Number of cores [${VASP_CORES}]: " CORES;     CORES="${CORES:-$VASP_CORES}"
read -rp "Queue/partition [${VASP_QUEUE}]: " QUEUE;     QUEUE="${QUEUE:-$VASP_QUEUE}"
read -rp "Walltime [${VASP_TIME}]: " TIME;              TIME="${TIME:-$VASP_TIME}"
read -rp "Account [${VASP_ACCOUNT}]: " ACCOUNT;         ACCOUNT="${ACCOUNT:-$VASP_ACCOUNT}"

CMD_ARGS=(-n "$NODES" -c "$CORES" -q "$QUEUE" -t "$TIME" -a "$ACCOUNT")

for dir in "${dirs[@]}"; do
    echo "▶ $dir"
    ( cd "$dir" && bash "${SCRIPT_DIR}/fd_phonons_job.sh" "${CMD_ARGS[@]}" )
    echo "----------------------------------------"
done
echo "All directories processed."
