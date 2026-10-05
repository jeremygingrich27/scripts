#!/bin/bash
# setup_phonon.sh — build the final/ phonon-workflow directory from finished
# convergence sweeps. It:
#   1. picks the converged ecut + k-mesh from the relax sweeps (pick_converged.py),
#   2. writes the tight final vc-relax + scf, seeded from the converged sweep
#      case (gen_final.py),
#   3. writes the ph.x / q2r.x / matdyn.x inputs (gen_ph.py).
# Run it from a run dir holding the sweep dirs, the base pseudos/, etc.
#
#   ./setup_phonon.sh --nq "4 4 4" --kpath kpath.dat                 # metal
#   ./setup_phonon.sh --nq "4 4 1" --epsil --kpath kpath.dat         # insulator
#   ./setup_phonon.sh --nq "4 4 4" --occupations smearing            # keep smearing
#
# --occupations {fixed,smearing,inherit} is passed to gen_final.py (default
# fixed; smearing uses gen_final's gaussian / 0.004 Ry defaults).
#
# The ecut/mesh are auto-picked (override with --ecut / --mesh). The relax + scf
# are seeded from the chosen k-mesh sweep case (override with --seed).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ecut_sweep="ecut_relax_sweep"
kpt_sweep="kpt_relax_sweep"
tol="0.001"
pseudos="pseudos"
outdir="final"
prefix="pwscf"
nq=""
kpath=""
epsil=""
ecut=""
mesh=""
seed=""
occupations="fixed"

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ecut-sweep) ecut_sweep="$2"; shift 2;;
        --kpt-sweep)  kpt_sweep="$2";  shift 2;;
        --tol)        tol="$2";        shift 2;;
        --pseudos)    pseudos="$2";    shift 2;;
        --outdir)     outdir="$2";     shift 2;;
        --prefix)     prefix="$2";     shift 2;;
        --nq)         nq="$2";         shift 2;;
        --kpath)      kpath="$2";      shift 2;;
        --epsil)      epsil="1";       shift 1;;
        --ecut)       ecut="$2";       shift 2;;
        --mesh)       mesh="$2";       shift 2;;
        --seed)       seed="$2";       shift 2;;
        --occupations) occupations="$2"; shift 2;;
        -h|--help)    usage 0;;
        *) echo "unknown argument: $1" >&2; usage 1;;
    esac
done

[[ -z "$nq" ]] && { echo "--nq (phonon q-grid, e.g. \"4 4 4\") is required" >&2; exit 1; }

# 1. pick converged ecut + k-mesh (the table goes to stderr, the value to stdout)
[[ -z "$ecut" ]] && ecut=$(python3 "$HERE/pick_converged.py" "$ecut_sweep" --tol "$tol" --bare)
[[ -z "$mesh" ]] && mesh=$(python3 "$HERE/pick_converged.py" "$kpt_sweep" --tol "$tol" --bare)

# 2. seed the relax/scf from the chosen k-mesh sweep case unless told otherwise
if [[ -z "$seed" ]]; then
    tag="${mesh// /x}"                       # "6 6 6" -> 6x6x6
    seed="$kpt_sweep/mesh_${tag}/scf.in"
fi
[[ -f "$seed" ]] || { echo "seed input not found: $seed (pass --seed)" >&2; exit 1; }

python3 "$HERE/gen_final.py" --input "$seed" --ecut "$ecut" --mesh "$mesh" \
    --outdir "$outdir" --pseudos "$pseudos" --prefix "$prefix" \
    --occupations "$occupations"

# 3. phonon inputs
ph_flags=(--outdir "$outdir" --prefix "$prefix" --nq "$nq")
[[ -n "$kpath" ]] && ph_flags+=(--kpath "$kpath")
[[ -n "$epsil" ]] && ph_flags+=(--epsil)
python3 "$HERE/gen_ph.py" "${ph_flags[@]}"

echo "done: $outdir/ ready (ecut=$ecut Ry, mesh=$mesh, q-grid=$nq, occupations=$occupations, seed=$seed)"
