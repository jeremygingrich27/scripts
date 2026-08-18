#!/usr/bin/env bash
# repeat_relax.sh
# Run VASP repeatedly in the current directory until the structure is converged
# (POSCAR ~ CONTCAR within tolerance). Checkpoints each iteration and resumes a
# previous run. Typically invoked from inside a SLURM job.
set -uo pipefail   # not -e: per-iteration failures are handled explicitly

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"
COMPARE="${SCRIPT_DIR}/compare_poscar_contcar.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Relax until POSCAR ~ CONTCAR. Run from a directory with VASP inputs.

Options:
      --max-iter N   maximum relaxation iterations          (default: 50)
      --tol VALUE    POSCAR/CONTCAR convergence tolerance   (default: 1e-8)
      --no-kpoints   skip per-iteration vaspkit KPOINTS regeneration
                     (keeps the k-point density as the cell relaxes)
  -h, --help         show this help and exit
USAGE
}

MAX_ITER=50
TOL="1e-8"
REGEN_KPOINTS=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --max-iter)   MAX_ITER="${2:?--max-iter needs a value}"; shift 2 ;;
        --tol)        TOL="${2:?--tol needs a value}";           shift 2 ;;
        --no-kpoints) REGEN_KPOINTS=0; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

need_file POSCAR; need_file INCAR
[[ -x "$COMPARE" || -f "$COMPARE" ]] || die "compare script not found: $COMPARE"

# VASP launcher: use ibrun on TACC, fall back to the bare binary elsewhere.
if command -v ibrun >/dev/null 2>&1; then RUN="ibrun ${VASP_BIN}"; else RUN="${VASP_BIN}"; fi

LOG_FILE="relaxation.log"
OUTPUT_DIR="relaxation_outputs"
ITER=0
result="false"
energy="N/A"

# ── Resume from a previous run if one is present ─────────────────────────────
if [[ -f "$LOG_FILE" && -d "$OUTPUT_DIR" ]]; then
    last_iter=$(ls -1 "$OUTPUT_DIR" 2>/dev/null | sed -n 's/^iter_//p' | sort -n | tail -1)
    if [[ -n "${last_iter:-}" && "$last_iter" -gt 0 ]]; then
        last_status=$(grep "^$last_iter " "$LOG_FILE" | tail -1 | awk '{print $4}')
        if [[ "$last_status" == "CONVERGED" ]]; then
            echo "Previous run already converged at iteration $last_iter"
            exit 0
        fi
        if [[ -f "$OUTPUT_DIR/iter_$last_iter/CONTCAR" ]]; then
            cp "$OUTPUT_DIR/iter_$last_iter/CONTCAR" POSCAR
            ITER=$last_iter
        fi
    fi
fi

mkdir -p "$OUTPUT_DIR"
if (( ITER == 0 )); then
    {
        echo "VASP Relaxation Log - $(date)"
        echo "tolerance=$TOL  max_iter=$MAX_ITER"
        echo "----------------------------------------"
        printf "%-6s %-15s %-15s %s\n" "Iter" "Energy(eV)" "Time(sec)" "Status"
        echo "----------------------------------------"
    } > "$LOG_FILE"
fi

# ── Relaxation loop ──────────────────────────────────────────────────────────
while (( ITER < MAX_ITER )); do
    ((ITER++))

    (( REGEN_KPOINTS )) && echo -e "102\n2\n0.03" | vaspkit >/dev/null 2>&1
    $RUN > relax.out 2>&1 || { echo "$ITER VASP failed" >> "$LOG_FILE"; break; }

    [[ -f CONTCAR ]] || { echo "$ITER CONTCAR missing" >> "$LOG_FILE"; break; }

    iter_dir="$OUTPUT_DIR/iter_$ITER"
    mkdir -p "$iter_dir"
    cp POSCAR CONTCAR OUTCAR OSZICAR "$iter_dir/" 2>/dev/null || true

    energy=$(grep "free  energy   TOTEN" OUTCAR | tail -1 | awk '{print $5}'); energy="${energy:-N/A}"
    elapsed=$(grep "Elapsed time (sec):" OUTCAR | tail -1 | awk '{print $4}'); elapsed="${elapsed:-N/A}"

    result=$(bash "$COMPARE" "$TOL" | tr -d '[:space:]')
    if [[ "$result" != "true" && "$result" != "false" ]]; then
        echo "$ITER Comparison failed" >> "$LOG_FILE"; result="false"; break
    fi

    status=$([[ "$result" == "true" ]] && echo "CONVERGED" || echo "CONTINUE")
    printf "%-6d %-15s %-15s %s\n" "$ITER" "$energy" "$elapsed" "$status" >> "$LOG_FILE"

    [[ "$result" == "true" ]] && break
    cp CONTCAR POSCAR
done

# ── Final status ─────────────────────────────────────────────────────────────
{
    echo "----------------------------------------"
    [[ "$result" == "true" ]] && echo "Converged after $ITER iterations" \
                              || echo "Stopped after $ITER iterations"
    echo "Final energy: $energy eV"
} | tee -a "$LOG_FILE"

[[ "$result" == "true" ]]
