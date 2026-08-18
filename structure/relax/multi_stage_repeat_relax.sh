#!/usr/bin/env bash
# multi_stage_repeat_relax.sh
# Multi-stage VASP relaxation: each stage sets its own ISIF/IBRION in the INCAR.
# Non-final stages run once; the final stage repeats until POSCAR ~ CONTCAR.
# Run from a directory containing POSCAR and INCAR (typically inside a SLURM job).
set -uo pipefail   # not -e: per-iteration failures are handled explicitly

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../lib/slurm_defaults.sh"
COMPARE="${SCRIPT_DIR}/compare_poscar_contcar.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options] STAGE [STAGE ...]

Each STAGE is ISIF:IBRION (or "(ISIF,IBRION)"). The last stage repeats until
the structure is converged; earlier stages run once.

Options:
      --tol VALUE    POSCAR/CONTCAR convergence tolerance  (default: 1e-6)
      --max-iter N   maximum total iterations              (default: 50)
  -h, --help         show this help and exit

Example:
  $(basename "$0") --tol 1e-6 3:2 1:3      # coarse ISIF=3, then fine ISIF=1
USAGE
}

TOL="1e-6"
MAX_ITER=50
STAGES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tol)      TOL="${2:?--tol needs a value}";      shift 2 ;;
        --max-iter) MAX_ITER="${2:?--max-iter needs a value}"; shift 2 ;;
        -h|--help)  usage; exit 0 ;;
        -*) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
        *)  # STAGE: ISIF:IBRION  or  (ISIF,IBRION)
            if [[ "$1" =~ ^\(([0-9]+),([0-9]+)\)$ || "$1" =~ ^([0-9]+):([0-9]+)$ ]]; then
                STAGES+=("${BASH_REMATCH[1]},${BASH_REMATCH[2]}")
            else
                die "invalid stage '$1' — use ISIF:IBRION or (ISIF,IBRION)"
            fi
            shift ;;
    esac
done

(( ${#STAGES[@]} > 0 )) || { usage >&2; die "at least one ISIF:IBRION stage is required"; }
need_file POSCAR; need_file INCAR
[[ -f "$COMPARE" ]] || die "compare script not found: $COMPARE"

if command -v ibrun >/dev/null 2>&1; then RUN="ibrun ${VASP_BIN}"; else RUN="${VASP_BIN}"; fi

LOG_FILE="relaxation.log"
OUTPUT_DIR="relaxation_outputs"
ITER=0
final_energy="N/A"; final_isif="N/A"; final_ibrion="N/A"; final_converged=false

# Back up the INCAR and always restore it on exit.
cp INCAR INCAR.original
cleanup() { [[ -f INCAR.original ]] && mv -f INCAR.original INCAR && echo "Restored original INCAR"; }
trap cleanup EXIT

# Write ISIF/IBRION into a fresh copy of the original INCAR.
update_incar() {
    local isif="$1" ibrion="$2"
    cp INCAR.original INCAR.tmp
    grep -q "^[[:space:]]*ISIF"   INCAR.tmp && sed -i "s/^[[:space:]]*ISIF[[:space:]]*=.*/ISIF   = $isif/"   INCAR.tmp || echo "ISIF   = $isif"   >> INCAR.tmp
    grep -q "^[[:space:]]*IBRION" INCAR.tmp && sed -i "s/^[[:space:]]*IBRION[[:space:]]*=.*/IBRION = $ibrion/" INCAR.tmp || echo "IBRION = $ibrion" >> INCAR.tmp
    mv INCAR.tmp INCAR
}

# Run VASP once, archive outputs, set $energy. Returns 1 on failure.
run_iter() {
    $RUN > vasp.out 2>&1 || { echo "$ITER VASP failed" >> "$LOG_FILE"; return 1; }
    [[ -f CONTCAR ]] || { echo "$ITER CONTCAR missing" >> "$LOG_FILE"; return 1; }
    local d="$OUTPUT_DIR/iter_$ITER"; mkdir -p "$d"
    cp POSCAR CONTCAR OUTCAR OSZICAR INCAR "$d/" 2>/dev/null || true
    energy=$(grep "free  energy   TOTEN" OUTCAR | tail -1 | awk '{print $5}'); energy="${energy:-N/A}"
    final_energy="$energy"
}

mkdir -p "$OUTPUT_DIR"
{
    echo "VASP Multi-Stage Relaxation Log - $(date)"
    echo "tolerance=$TOL  max_iter=$MAX_ITER  stages=${STAGES[*]}"
    echo "========================================"
    printf "%-6s %-8s %-15s %-12s %s\n" "Iter" "Stage" "Energy(eV)" "ISIF/IBRION" "Status"
    echo "========================================"
} > "$LOG_FILE"

for idx in "${!STAGES[@]}"; do
    IFS=',' read -r isif ibrion <<< "${STAGES[$idx]}"
    final_isif="$isif"; final_ibrion="$ibrion"
    update_incar "$isif" "$ibrion"
    echo "Stage $((idx+1)): ISIF=$isif IBRION=$ibrion" | tee -a "$LOG_FILE"

    if (( idx == ${#STAGES[@]} - 1 )); then
        # Final stage: repeat until converged.
        while (( ITER < MAX_ITER )); do
            ((ITER++))
            run_iter || break
            result=$(bash "$COMPARE" "$TOL" | tr -d '[:space:]')
            [[ "$result" == "true" || "$result" == "false" ]] || { echo "$ITER Comparison failed" >> "$LOG_FILE"; break; }
            status=$([[ "$result" == "true" ]] && echo "CONVERGED" || echo "CONTINUE")
            printf "%-6d %-8s %-15s %-12s %s\n" "$ITER" "$((idx+1))" "$final_energy" "$isif/$ibrion" "$status" >> "$LOG_FILE"
            [[ "$result" == "true" ]] && { final_converged=true; break; }
            cp CONTCAR POSCAR
        done
    else
        # Earlier stage: run once.
        ((ITER++))
        run_iter || break
        printf "%-6d %-8s %-15s %-12s %s\n" "$ITER" "$((idx+1))" "$final_energy" "$isif/$ibrion" "STAGE_COMPLETE" >> "$LOG_FILE"
        cp CONTCAR POSCAR
    fi
done

{
    echo "========================================"
    [[ "$final_converged" == "true" ]] && echo "Converged after $ITER total iterations" \
                                       || echo "Stopped after $ITER total iterations"
    echo "Final energy: $final_energy eV"
    echo "Final parameters: ISIF=$final_isif IBRION=$final_ibrion  (tol=$TOL)"
} | tee -a "$LOG_FILE"

[[ "$final_converged" == "true" ]]
