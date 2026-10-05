#!/bin/bash
# setup_convergence.sh — wrapper that builds the convergence sweep directories
# by calling the per-sweep Python generators. Run it from a directory holding a
# base scf.in and a pseudos/ subdirectory.
#
# It exposes the union of the generators' arguments. A sweep is built only if
# its values are supplied (--ecuts and/or --kn). --mode selects scf or vc-relax
# inputs (--cell-dofree / --press apply only to relax mode).
#
#   ./setup_convergence.sh --mode relax --ecuts "60 70 80 90" \
#       --kn "2 4 6" --kratio auto --cell-dofree all
#
set -euo pipefail

# locate the generators next to this script, regardless of where it's run from
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

input="scf.in"
pseudos="pseudos"
mode="scf"            # scf | relax
ecuts=""
kn=""
kratio="1 1 1"
cell_dofree="all"
press=""

usage() {
    grep '^#' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)        input="$2";        shift 2;;
        --pseudos)      pseudos="$2";      shift 2;;
        --mode)         mode="$2";         shift 2;;
        --ecuts)        ecuts="$2";        shift 2;;
        --kn)           kn="$2";           shift 2;;
        --kratio)       kratio="$2";       shift 2;;
        --cell-dofree)  cell_dofree="$2";  shift 2;;
        --press)        press="$2";        shift 2;;
        -h|--help)      usage 0;;
        *) echo "unknown argument: $1" >&2; usage 1;;
    esac
done

if [[ "$mode" != "scf" && "$mode" != "relax" ]]; then
    echo "--mode must be 'scf' or 'relax'" >&2; exit 1
fi
if [[ -z "$ecuts" && -z "$kn" ]]; then
    echo "nothing to do: give --ecuts and/or --kn" >&2; exit 1
fi

# extra flags only meaningful in relax mode
relax_flags=(--cell-dofree "$cell_dofree")
[[ -n "$press" ]] && relax_flags+=(--press "$press")

if [[ -n "$ecuts" ]]; then
    if [[ "$mode" == "relax" ]]; then
        python3 "$HERE/gen_ecut_relax.py" --input "$input" --pseudos "$pseudos" \
            --ecuts "$ecuts" "${relax_flags[@]}"
    else
        python3 "$HERE/gen_ecut.py" --input "$input" --pseudos "$pseudos" \
            --ecuts "$ecuts"
    fi
fi

if [[ -n "$kn" ]]; then
    if [[ "$mode" == "relax" ]]; then
        python3 "$HERE/gen_kpoints_relax.py" --input "$input" --pseudos "$pseudos" \
            --kn "$kn" --kratio "$kratio" "${relax_flags[@]}"
    else
        python3 "$HERE/gen_kpoints.py" --input "$input" --pseudos "$pseudos" \
            --kn "$kn" --kratio "$kratio"
    fi
fi

echo "done."
