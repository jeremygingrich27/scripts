#!/usr/bin/env bash
# write_minima_jobscripts.sh
# Write per-stage VASP jobscripts into a tree built by setup_minima_dos.sh,
# plus a submit_all.sh that chains dos/bands after scf via --dependency=afterok.
#
# One jobscript per stage rather than one chained job per structure: scf and
# the NSCF stages want different node counts, so chaining would over-allocate
# one of them.
#
# Default walltimes are measured, not guessed. From the reference runs in
# AFII_electronic_bands/orbital_projected/ (same 64-atom cell, ENCUT 700):
#   scf    2x256  3.71-3.95 h  (21-24 electronic steps, NELM=200)
#   dos    4x256  1.47-1.50 h  (11 steps; ICHARG=11 is non-self-consistent)
#   bands  8x512  0.87-0.89 h  (11 steps)
# The NSCF stages take a fixed step count so their margin can be tight. The
# SCF step count is the variable one, so it carries the headroom.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../../lib/slurm_defaults.sh"

TABLE="./minima_table.tsv"
ROOT="."
SCF_NODES=2;   SCF_CORES=256;   SCF_TIME="08:00:00"
DOS_NODES=4;   DOS_CORES=256;   DOS_TIME="03:00:00"
BND_NODES=8;   BND_CORES=512;   BND_TIME="02:00:00"

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Writes <ROOT>/<label>/<stage>/jobscript for every row of the table, and
<ROOT>/submit_all.sh.

Options:
      --table FILE     minima table TSV              (default: ${TABLE})
      --root DIR       tree root                     (default: ${ROOT})
      --scf-time T     scf walltime                  (default: ${SCF_TIME})
      --dos-time T     dos walltime                  (default: ${DOS_TIME})
      --bands-time T   bands walltime                (default: ${BND_TIME})
      --scf-nodes N    scf nodes                     (default: ${SCF_NODES})
      --dos-nodes N    dos nodes                     (default: ${DOS_NODES})
      --bands-nodes N  bands nodes                   (default: ${BND_NODES})
      --scf-cores N    scf tasks                     (default: ${SCF_CORES})
      --dos-cores N    dos tasks                     (default: ${DOS_CORES})
      --bands-cores N  bands tasks                   (default: ${BND_CORES})
  -h, --help           show this help and exit

Cores default to the 64-atom AFII sizing; a smaller cell needs them lowered to
match the node count (LS6 is 128 cores/node) or SLURM over-subscribes.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --table)       TABLE="${2:?}";      shift 2 ;;
        --root)        ROOT="${2:?}";       shift 2 ;;
        --scf-time)    SCF_TIME="${2:?}";   shift 2 ;;
        --dos-time)    DOS_TIME="${2:?}";   shift 2 ;;
        --bands-time)  BND_TIME="${2:?}";   shift 2 ;;
        --scf-nodes)   SCF_NODES="${2:?}";  shift 2 ;;
        --dos-nodes)   DOS_NODES="${2:?}";  shift 2 ;;
        --bands-nodes) BND_NODES="${2:?}";  shift 2 ;;
        --scf-cores)   SCF_CORES="${2:?}";  shift 2 ;;
        --dos-cores)   DOS_CORES="${2:?}";  shift 2 ;;
        --bands-cores) BND_CORES="${2:?}";  shift 2 ;;
        -h|--help)     usage; exit 0 ;;
        *) die "unknown option '$1'" ;;
    esac
done

need_file "$TABLE" "minima table"

# ---- stage bodies -----------------------------------------------------------
# scf: plain run. NSCF: refuse to start unless the SCF finished, then take its
# charge density (METHODS section 3).
scf_body() {
    cat <<'BODY'

cd "$SLURM_SUBMIT_DIR"
ibrun vasp_std
BODY
}

nscf_body() {
    cat <<'BODY'

cd "$SLURM_SUBMIT_DIR"
if ! grep -q "General timing and accounting" ../scf/OUTCAR 2>/dev/null; then
    echo "ERROR: SCF (../scf/OUTCAR) did not finish cleanly - aborting" >&2
    exit 1
fi
cp ../scf/CHGCAR .
ibrun vasp_std
BODY
}

write_stage() {                     # write_stage DIR NAME NODES CORES TIME BODYFN
    local dir="$1" name="$2" nodes="$3" cores="$4" time="$5" bodyfn="$6"
    [[ -d "$dir" ]] || return 0
    { vasp_slurm_header "$name" "$nodes" "$cores" "$VASP_QUEUE" "$time" "$VASP_ACCOUNT"
      "$bodyfn"; } > "${dir}/jobscript"
    chmod +x "${dir}/jobscript"
}

# ---- walk the table ---------------------------------------------------------
read -r header < "$TABLE"
IFS=$'\t' read -r -a cols <<< "$header"
lab_i=-1; bands_i=-1
for i in "${!cols[@]}"; do
    [[ "${cols[i]}" == "label" ]] && lab_i=$i
    [[ "${cols[i]}" == "bands" ]] && bands_i=$i
done
(( lab_i >= 0 && bands_i >= 0 )) || die "table needs 'label' and 'bands' columns"

LABELS=(); n=0
while IFS=$'\t' read -r -a f; do
    label="${f[lab_i]}"
    [[ -z "$label" ]] && continue
    LABELS+=("$label")
    write_stage "${ROOT}/${label}/scf"   "${label}_scf"   "$SCF_NODES" "$SCF_CORES" "$SCF_TIME" scf_body
    write_stage "${ROOT}/${label}/dos"   "${label}_dos"   "$DOS_NODES" "$DOS_CORES" "$DOS_TIME" nscf_body
    write_stage "${ROOT}/${label}/bands" "${label}_bands" "$BND_NODES" "$BND_CORES" "$BND_TIME" nscf_body
    n=$((n+1))
done < <(tail -n +2 "$TABLE")

# ---- submit_all.sh ----------------------------------------------------------
{
    cat <<'HDR'
#!/usr/bin/env bash
# submit_all.sh - submit every structure: scf first, then dos (and bands)
# held until the scf completes successfully.
set -euo pipefail
cd "$(dirname "$0")"

# TACC's sbatch wrapper prints its "Welcome to Lonestar6" validation banner to
# STDOUT, so a bare $(sbatch --parsable ...) captures the banner along with the
# job id. Keep only the trailing all-digit line, and refuse to continue if that
# does not look like a job id -- otherwise the garbage silently becomes an
# invalid --dependency argument.
submit() {                       # submit DIR [extra sbatch args...]
    local dir="$1"; shift
    local out jid
    out=$( cd "$dir" && sbatch --parsable "$@" jobscript 2>&1 ) || {
        echo "ERROR: sbatch failed in $dir:" >&2; echo "$out" >&2; return 1; }
    jid=$( printf '%s\n' "$out" | tr -d '\r' | grep -oE '^[0-9]+' | tail -n1 )
    [[ "$jid" =~ ^[0-9]+$ ]] || {
        echo "ERROR: could not parse a job id from sbatch in $dir:" >&2
        echo "$out" >&2; return 1; }
    printf '%s' "$jid"
}

queued() {                       # queued JOBNAME -> 0 if already in the queue
    squeue -u "$USER" -h -o '%j' 2>/dev/null | grep -qx -- "$1"
}

for d in \
HDR
    printf '    %s \\\n' "${LABELS[@]}"
    cat <<'TAIL'
    ; do
    [[ -d "$d/scf" ]] || { echo "skip $d (no scf/)"; continue; }

    # Already in the queue? Skip, so re-running after a partial failure is safe.
    if queued "${d}_scf"; then
        echo "skip $d (${d}_scf already queued)"
        continue
    fi

    jid_scf=$( submit "$d/scf" )
    echo "$d  scf=$jid_scf"
    for stage in dos bands; do
        [[ -d "$d/$stage" ]] || continue
        jid=$( submit "$d/$stage" --dependency=afterok:"$jid_scf" )
        echo "$d  $stage=$jid  (after $jid_scf)"
    done
done
TAIL
} > "${ROOT}/submit_all.sh"
chmod +x "${ROOT}/submit_all.sh"

echo "Wrote jobscripts for ${n} structure(s) and ${ROOT}/submit_all.sh"
