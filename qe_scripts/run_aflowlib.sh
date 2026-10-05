#!/bin/bash
# run_aflowlib.sh — run the convergence sweeps interactively on aflowlib.
# No scheduler, no modules: pw.x is already on PATH and launched with mpirun.
# Run it from the directory that holds the generated sweep subdirectories
# (i.e. where you ran setup_convergence.sh).
#
#   ./run_aflowlib.sh --mode relax --np 4
#   ./run_aflowlib.sh --mode scf   --np 8 --dirs "ecut_sweep/*"
#
# scf mode runs one pw.x per case. relax mode runs the iterative vc-relax,
# feeding the relaxed structure back via update_structure.py until the cell and
# atomic positions are self-consistent or --max-iter is reached.
#
# Note: no `set -e` on purpose — a failed pw.x must NOT abort the script, so
# update_structure.py can report it and the loop can move on.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mode="relax"
np=4
pw="pw.x"
dirs=""
maxiter=5
cell_thr=0.01
angle_thr=0.05
pos_thr=0.01

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)      mode="$2";      shift 2;;
        --np)        np="$2";        shift 2;;
        --pw)        pw="$2";        shift 2;;
        --dirs)      dirs="$2";      shift 2;;
        --max-iter)  maxiter="$2";   shift 2;;
        --cell-thr)  cell_thr="$2";  shift 2;;
        --angle-thr) angle_thr="$2"; shift 2;;
        --pos-thr)   pos_thr="$2";   shift 2;;
        -h|--help)   usage 0;;
        *) echo "unknown argument: $1" >&2; usage 1;;
    esac
done

if [[ "$mode" != "scf" && "$mode" != "relax" ]]; then
    echo "--mode must be 'scf' or 'relax'" >&2; exit 1
fi
if [[ -z "$dirs" ]]; then
    [[ "$mode" == "relax" ]] && dirs="ecut_relax_sweep/* kpt_relax_sweep/*" \
                             || dirs="ecut_sweep/* kpt_sweep/*"
fi

launch="mpirun -np $np $pw"
echo "launcher: $launch"

for d in $dirs; do
    [ -f "$d/scf.in" ] || continue
    echo "=== $d ==="
    if [[ "$mode" == "scf" ]]; then
        ( cd "$d"; export ESPRESSO_TMPDIR="$PWD/out"; mkdir -p "$ESPRESSO_TMPDIR"
          $launch < scf.in > scf.out )
    else
        ( cd "$d"
          export ESPRESSO_TMPDIR="$PWD/out"; mkdir -p "$ESPRESSO_TMPDIR"
          for i in $(seq 1 "$maxiter"); do
              echo "  vc-relax iteration $i"
              $launch < scf.in > scf.out
              python3 "$HERE/update_structure.py" scf.in scf.out --iter "$i" \
                  --cell-thr "$cell_thr" --angle-thr "$angle_thr" --pos-thr "$pos_thr"
              rc=$?
              [ "$rc" -eq 0 ] && { echo "  converged after $i iteration(s)"; break; }
              [ "$rc" -eq 2 ] && { echo "  run did not finish — stopping this case"; break; }
              # rc == 1: structure updated, run again
          done )
    fi
done
echo "all cases done."
