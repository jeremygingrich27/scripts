#!/usr/bin/env bash
# submit_jobs.sh
# Submit a jobscript found in subdirectories. Merges the old submit_multiple.sh
# (recursive search for files named "jobscript") and submit_job_loop.sh (submit
# a named jobscript in each immediate subdirectory).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Submit a jobscript in each matching subdirectory (with confirmation).

Options:
      --name NAME    jobscript filename to submit   (default: jobscript)
  -r, --recursive    search subdirectories at any depth
                     (default: immediate subdirectories only)
  -y, --yes          skip the confirmation prompt
  -h, --help         show this help and exit

Examples:
  $(basename "$0")                      # submit ./*/jobscript, after confirming
  $(basename "$0") --name relax.slurm   # submit a differently named file
  $(basename "$0") -r -y                # recursive, no confirmation
USAGE
}

NAME="jobscript"
RECURSIVE=0
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name)          NAME="${2:?--name needs a value}"; shift 2 ;;
        -r|--recursive)  RECURSIVE=1; shift ;;
        -y|--yes)        ASSUME_YES=1; shift ;;
        -h|--help)       usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

ROOT="$PWD"

# ── Collect target directories (those containing $NAME) ─────────────────────
JOB_DIRS=()
if (( RECURSIVE )); then
    while IFS= read -r -d '' path; do
        JOB_DIRS+=("$(dirname "$path")")
    done < <(find . -type f -name "$NAME" -print0 | sort -z)
else
    for dir in */; do
        [[ -f "${dir}${NAME}" ]] && JOB_DIRS+=("${dir%/}")
    done
fi

(( ${#JOB_DIRS[@]} > 0 )) || die "no '${NAME}' found in $( ((RECURSIVE)) && echo 'any subdirectory' || echo 'immediate subdirectories' ) of ${ROOT}"

echo "Will submit '${NAME}' in ${#JOB_DIRS[@]} director$( (( ${#JOB_DIRS[@]} == 1 )) && echo y || echo ies ):"
printf '  %s\n' "${JOB_DIRS[@]}"
echo

if (( ! ASSUME_YES )); then
    confirm "Submit all of these?" || { echo "Aborted."; exit 0; }
fi

# ── Submit ───────────────────────────────────────────────────────────────────
submitted=0 failed=0
for dir in "${JOB_DIRS[@]}"; do
    echo ">> ${dir}"
    if ( cd "$dir" && sbatch "$NAME" ); then
        ((submitted++))
    else
        echo "   ✗ submission failed" >&2
        ((failed++))
    fi
done

echo
echo "Done. Submitted: ${submitted}  Failed: ${failed}  Total: ${#JOB_DIRS[@]}"
(( failed == 0 ))
