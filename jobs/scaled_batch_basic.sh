#!/usr/bin/env bash
# scaled_batch_basic.sh
# Build (and optionally submit) a SLURM job that runs VASP in each
# POSCAR_scaled_*/ directory in sequence, then parses the results.
# Run from a CALC directory containing POSCAR_scaled_*/ subdirectories.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"

JOBSCRIPT="chain_vasp_jobscript.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes ${JOBSCRIPT} chaining VASP over POSCAR_scaled_*/ directories.

Options:
      --dirs "A B C"   directories to chain, in order (default: all POSCAR_scaled_*, sorted)
      --copy "F1 F2"   files to copy forward between steps (e.g. "CHGCAR WAVECAR")
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
TIME="${VASP_TIME}";   ACCOUNT="${VASP_ACCOUNT}"
DIRS_ARG=""; COPY_ARG=""; SUBMIT=0; INTERACTIVE=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dirs)       DIRS_ARG="${2:?--dirs needs a value}"; shift 2 ;;
        --copy)       COPY_ARG="${2:?--copy needs a value}"; shift 2 ;;
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

# ── Resolve directories to chain ─────────────────────────────────────────────
DIRS=()
if [[ -n "$DIRS_ARG" ]]; then
    read -r -a DIRS <<< "$DIRS_ARG"
else
    mapfile -t SCALED < <(find . -maxdepth 1 -type d -name "POSCAR_scaled_*" -printf '%f\n' | sort)
    (( ${#SCALED[@]} > 0 )) || die "no POSCAR_scaled_*/ directories found in $PWD"
    if (( INTERACTIVE )); then
        echo "POSCAR_scaled_*/ directories:"
        for i in "${!SCALED[@]}"; do printf "  %2d) %s\n" "$((i+1))" "${SCALED[i]}"; done
        read -rp "Indices to chain (e.g. 1 3 4), or Enter for ALL: " -a picks
        if (( ${#picks[@]} == 0 )); then
            DIRS=("${SCALED[@]}")
        else
            for p in "${picks[@]}"; do
                [[ "$p" =~ ^[0-9]+$ ]] && (( p>=1 && p<=${#SCALED[@]} )) || die "invalid index: $p"
                DIRS+=("${SCALED[$((p-1))]}")
            done
        fi
    else
        DIRS=("${SCALED[@]}")
    fi
fi
(( ${#DIRS[@]} > 0 )) || die "no directories selected"
for d in "${DIRS[@]}"; do [[ -d "$d" ]] || die "directory not found: $d"; done

# ── Files to copy forward ────────────────────────────────────────────────────
COPY=()
if [[ -n "$COPY_ARG" ]]; then
    read -r -a COPY <<< "$COPY_ARG"
elif (( INTERACTIVE )); then
    confirm "Copy CHGCAR between steps?" && COPY+=("CHGCAR")
    confirm "Copy WAVECAR between steps?" && COPY+=("WAVECAR")
fi

echo
echo "Chaining ${#DIRS[@]} directories:"; printf '  %s\n' "${DIRS[@]}"
echo "Copying forward: ${COPY[*]:-(none)}"
echo

DIRS_LITERAL=$(printf '"%s" ' "${DIRS[@]}")
COPY_LITERAL=$(printf '"%s" ' "${COPY[@]}")

vasp_slurm_header "chain_vasp" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > "$JOBSCRIPT"
cat >> "$JOBSCRIPT" <<EOF

ROOT="\$PWD"
DIRS=($DIRS_LITERAL)
FILES_TO_COPY=($COPY_LITERAL)

for ((i=0; i<\${#DIRS[@]}; i++)); do
  CUR="\${DIRS[i]}"
  if [[ -f "\$CUR/COMPLETED" ]]; then
    echo "Skipping \$CUR (already completed)"
    continue
  fi
  echo "▶ Step \$((i+1))/\${#DIRS[@]} : \$CUR"
  cd "\$CUR"
  if (( i > 0 && \${#FILES_TO_COPY[@]} > 0 )); then
    for f in "\${FILES_TO_COPY[@]}"; do
      cp -f "\$ROOT/\${DIRS[i-1]}/\$f" "\$f" 2>/dev/null || echo "  (no \$f to copy forward)"
    done
  fi
  ibrun ${VASP_BIN}
  rc=\$?
  (( rc != 0 )) && { echo "❌ VASP failed (code \$rc) in \$CUR"; exit \$rc; }
  touch COMPLETED
  cd "\$ROOT"
done

echo "🎉 All calculations finished successfully."
bash ~/scripts/util/parse_data.sh
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
