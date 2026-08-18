#!/usr/bin/env bash
# write_chain_vasp_jobscript.sh
# Build a SLURM job that runs VASP in several subdirectories in sequence,
# optionally copying files (CHGCAR/WAVECAR/...) forward between steps.
# Run from a directory whose subdirectories each hold a full VASP input set
# (POSCAR, POTCAR, KPOINTS, INCAR).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"

JOBSCRIPT="chain_vasp_jobscript.sh"
JOBNAME="chain_vasp"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes ${JOBSCRIPT} chaining VASP over subdirectories. Interactive by default;
flags make it scriptable.

Options:
      --dirs "A B C"   directories to chain, in order (default: choose interactively)
      --copy "F1 F2"   files to copy forward between steps (e.g. "CHGCAR WAVECAR")
      --out FILE       jobscript filename to write  (default: ${JOBSCRIPT})
      --name NAME      SLURM job name (-J)          (default: ${JOBNAME})
  -N, --nodes N        nodes        (default: ${VASP_NODES})
  -n, --cores N        cores        (default: ${VASP_CORES})
  -q, --queue NAME     partition    (default: ${VASP_QUEUE})
  -t, --time HH:MM:SS  walltime     (default: ${VASP_TIME})
  -A, --account NAME   allocation   (default: ${VASP_ACCOUNT})
      --submit         submit the jobscript after writing it (asks to confirm)
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
        --out)        JOBSCRIPT="${2:?--out needs a value}"; shift 2 ;;
        --name)       JOBNAME="${2:?--name needs a value}";  shift 2 ;;
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

has_vasp_inputs() { [[ -f "$1/POSCAR" && -f "$1/POTCAR" && -f "$1/KPOINTS" && -f "$1/INCAR" ]]; }

# ── Resolve the list of directories to chain ────────────────────────────────
DIRS=()
if [[ -n "$DIRS_ARG" ]]; then
    read -r -a DIRS <<< "$DIRS_ARG"
else
    mapfile -t VALID < <(for d in */; do d="${d%/}"; has_vasp_inputs "$d" && echo "$d"; done | sort)
    (( ${#VALID[@]} > 0 )) || die "no subdirectories with a full VASP input set (POSCAR/POTCAR/KPOINTS/INCAR) found"
    if (( INTERACTIVE )); then
        echo "Directories with a full VASP input set:"
        for i in "${!VALID[@]}"; do printf "  %2d) %s\n" "$((i+1))" "${VALID[i]}"; done
        read -rp "Indices to chain, in order (e.g. 1 3 4): " -a picks
        for p in "${picks[@]}"; do
            [[ "$p" =~ ^[0-9]+$ ]] && (( p>=1 && p<=${#VALID[@]} )) || die "invalid index: $p"
            DIRS+=("${VALID[$((p-1))]}")
        done
    else
        DIRS=("${VALID[@]}")   # -y with no --dirs: chain all, in sorted order
    fi
fi
(( ${#DIRS[@]} > 0 )) || die "no directories selected"
for d in "${DIRS[@]}"; do has_vasp_inputs "$d" || die "missing VASP inputs in: $d"; done

# ── Resolve files to copy forward ────────────────────────────────────────────
COPY=()
if [[ -n "$COPY_ARG" ]]; then
    read -r -a COPY <<< "$COPY_ARG"
elif (( INTERACTIVE )); then
    confirm "Copy CHGCAR between steps?" && COPY+=("CHGCAR")
    confirm "Copy WAVECAR between steps?" && COPY+=("WAVECAR")
    read -rp "Any other files to copy forward (space-separated, blank for none): " -a extra
    (( ${#extra[@]} )) && COPY+=("${extra[@]}")
fi

echo
echo "Chaining ${#DIRS[@]} directories:"; printf '  %s\n' "${DIRS[@]}"
echo "Copying forward: ${COPY[*]:-(none)}"
echo

DIRS_LITERAL=$(printf '"%s" ' "${DIRS[@]}")
COPY_LITERAL=$(printf '"%s" ' "${COPY[@]}")

# ── Write the jobscript (shared header + chain body) ─────────────────────────
vasp_slurm_header "$JOBNAME" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > "$JOBSCRIPT"
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

echo "🎉 Chain complete."
bash ~/scripts/util/parse_data.sh -x
EOF

echo "✅ Jobscript written to ./${JOBSCRIPT}"

# ── Optional submit (confirm unless -y) ──────────────────────────────────────
if (( SUBMIT )); then
    if (( INTERACTIVE )) && ! confirm "Submit ${JOBSCRIPT} now?"; then
        echo "Not submitted. Run: sbatch ${JOBSCRIPT}"
    else
        sbatch "$JOBSCRIPT"
    fi
else
    echo "Submit with: sbatch ${JOBSCRIPT}"
fi
