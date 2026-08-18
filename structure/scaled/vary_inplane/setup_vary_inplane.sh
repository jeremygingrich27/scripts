#!/usr/bin/env bash
# setup_vary_inplane.sh
# Build the AFII vary_inplane tree of re-runnable, CHGCAR-seeded VASP decks.
#
# For each in-plane scale s, two disjoint c-axis chains are laid out:
#   compressed branch (d_z2)     : z ascending  0.80 -> 1.00
#   elongated  branch (d_x2-y2)  : z descending 1.30 -> 1.01
# The first dir of each chain gets INCAR.seed (ICHARG=2, cold start); every
# other dir gets INCAR.prop (ICHARG=1, reads the CHGCAR copied forward by the
# chain jobscript). Structures are scaled from POSCAR_ref via poscar_scaler.py.
#
# Assets expected next to this script: POSCAR_ref, INCAR.seed, INCAR.prop,
# KPOINTS, POTCAR. Chain jobscripts are added by the Piece-4 step.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../../../lib/slurm_defaults.sh"
PSCALER="${SCRIPT_DIR}/../../editor/poscar_scaler.py"
WCHAIN="${SCRIPT_DIR}/../../../jobs/write_chain_vasp_jobscript.sh"

# ---- defaults (all overridable) --------------------------------------------
SCALES_SPEC="0.95:1.05:0.01"   # in-plane scales  (list "a b c" or range start:stop:step)
ZC_SPEC="0.80:1.00:0.01"       # compressed z-sweep (used ASCENDING)
ZE_SPEC="1.01:1.30:0.01"       # elongated  z-sweep (used DESCENDING)
OUT="./vary_inplane_rebuild"
CHAIN_TIME="${VASP_TIME}"      # walltime per branch chain jobscript
MAKE_JOBS=1                    # also write per-scale chain jobscripts
ASSUME_YES=0

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Builds \$OUT/vary_inplane_lattice_scale_<s>/POSCAR_z_<z>/ input decks for the
AFII compressed + elongated c-axis seeding chains.

Options:
      --scales SPEC   in-plane scales; list "0.95 1.0" or range a:b:step
                      (default: ${SCALES_SPEC})
      --zc SPEC       compressed z-sweep, applied ascending  (default: ${ZC_SPEC})
      --ze SPEC       elongated  z-sweep, applied descending (default: ${ZE_SPEC})
      --out DIR       output root                             (default: ${OUT})
      --time HH:MM:SS chain jobscript walltime                (default: ${CHAIN_TIME})
      --no-jobscripts build decks only, skip chain jobscripts
  -y, --yes           don't prompt if OUT already exists
  -h, --help          show this help and exit
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scales) SCALES_SPEC="${2:?--scales needs a value}"; shift 2 ;;
        --zc)     ZC_SPEC="${2:?--zc needs a value}";         shift 2 ;;
        --ze)     ZE_SPEC="${2:?--ze needs a value}";         shift 2 ;;
        --out)    OUT="${2:?--out needs a value}";            shift 2 ;;
        --time)   CHAIN_TIME="${2:?--time needs a value}";    shift 2 ;;
        --no-jobscripts) MAKE_JOBS=0; shift ;;
        -y|--yes) ASSUME_YES=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

# ---- validate assets --------------------------------------------------------
need_cmd python3
for f in POSCAR_ref INCAR.seed INCAR.prop KPOINTS POTCAR; do
    need_file "${SCRIPT_DIR}/${f}" "asset ${f}"
done
need_file "$PSCALER" "poscar_scaler.py"
(( MAKE_JOBS )) && need_file "$WCHAIN" "write_chain_vasp_jobscript.sh"

# ---- helpers ----------------------------------------------------------------
# gen_values SPEC : emit values rounded to 0.01, one per line, in the order the
# spec implies for a list; ranges are emitted ascending (caller reorders).
gen_values() {
    local spec="$1"
    if [[ "$spec" == *:* ]]; then
        IFS=':' read -r a b s <<< "$spec"
        awk -v a="$a" -v b="$b" -v s="$s" 'BEGIN{
            n=int((b-a)/s + 0.5);
            for(i=0;i<=n;i++){ v=a+i*s; v=int(v*100 + (v<0?-0.5:0.5))/100; printf "%g\n", v }
        }'
    else
        local x; for x in $spec; do awk -v v="$x" 'BEGIN{printf "%g\n", int(v*100+0.5)/100}'; done
    fi
}

# ---- resolve value lists ----------------------------------------------------
mapfile -t SCALES < <(gen_values "$SCALES_SPEC")
mapfile -t ZC     < <(gen_values "$ZC_SPEC")                 # ascending
mapfile -t ZE     < <(gen_values "$ZE_SPEC" | sort -gr)      # descending
(( ${#SCALES[@]} && ${#ZC[@]} && ${#ZE[@]} )) || die "empty scale or z list"

a0=$(awk 'NR==3{print $1}' "${SCRIPT_DIR}/POSCAR_ref")

echo "Reference a0 = ${a0}"
echo "In-plane scales (${#SCALES[@]}): ${SCALES[*]}"
echo "Compressed z  (${#ZC[@]}, asc, seed=${ZC[0]}):  ${ZC[*]}"
echo "Elongated  z  (${#ZE[@]}, desc, seed=${ZE[0]}): ${ZE[*]}"
echo "Output root: ${OUT}"
echo

if [[ -d "$OUT" ]] && (( ! ASSUME_YES )); then
    confirm "OUT '$OUT' exists — write into it?" || die "aborted"
fi

# ---- build ------------------------------------------------------------------
# build_chain SCALE SEED_Z_INDEX0 z...   (branch name for the seed decision)
build_branch() {   # $1=scale  $2=Sdir  $3=branch label  shift 3 -> z-list in chain order
    local s="$1" Sdir="$2" branch="$3"; shift 3
    local first=1 z zdir
    for z in "$@"; do
        zdir="${Sdir}/POSCAR_z_${z}"
        mkdir -p "$zdir"
        python3 "$PSCALER" single "${SCRIPT_DIR}/POSCAR_ref" "$s" "$s" "$z" -o "${zdir}/POSCAR" >/dev/null
        sed -i "1s|.*|t-CuO AFII vary_inplane  scale=${s}  z=${z}  branch=${branch}|" "${zdir}/POSCAR"
        cp "${SCRIPT_DIR}/KPOINTS" "${SCRIPT_DIR}/POTCAR" "$zdir/"
        if (( first )); then cp "${SCRIPT_DIR}/INCAR.seed" "${zdir}/INCAR"; first=0
        else                 cp "${SCRIPT_DIR}/INCAR.prop" "${zdir}/INCAR"; fi
    done
}

# dir-list strings in chain order (ZC ascending, ZE descending)
comp_dirs=""; for z in "${ZC[@]}"; do comp_dirs+="POSCAR_z_${z} "; done
elon_dirs=""; for z in "${ZE[@]}"; do elon_dirs+="POSCAR_z_${z} "; done

for s in "${SCALES[@]}"; do
    Sdir="${OUT}/vary_inplane_lattice_scale_${s}"
    build_branch "$s" "$Sdir" compressed "${ZC[@]}"
    build_branch "$s" "$Sdir" elongated  "${ZE[@]}"
    if (( MAKE_JOBS )); then
        ( cd "$Sdir" && \
          bash "$WCHAIN" -y --dirs "$comp_dirs" --copy CHGCAR \
               --out jobscript_compressed --name "vip_${s}_comp" -t "$CHAIN_TIME" >/dev/null && \
          bash "$WCHAIN" -y --dirs "$elon_dirs" --copy CHGCAR \
               --out jobscript_elongated  --name "vip_${s}_elng" -t "$CHAIN_TIME" >/dev/null )
    fi
    echo "  built scale ${s}: $(find "$Sdir" -name INCAR | wc -l) decks$( (( MAKE_JOBS )) && echo ' + 2 jobscripts')"
done

n_scale=${#SCALES[@]}; per=$(( ${#ZC[@]} + ${#ZE[@]} ))
echo
echo "Done: ${n_scale} scales x ${per} z-points = $(( n_scale * per )) decks under ${OUT}"
(( MAKE_JOBS )) && echo "      + ${n_scale} x 2 chain jobscripts (jobscript_compressed / jobscript_elongated)"
echo "Next: rsync ${OUT} to \$WORK on TACC, then in each scale dir: sbatch jobscript_compressed jobscript_elongated"
