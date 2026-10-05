#!/bin/bash
# make_jobscript.sh — write a TACC SLURM jobscript that loops over the sweep
# subdirectories and runs pw.x in each. The launch command you pass with --ibrun
# is written verbatim into the jobscript (no $PW_EXEC indirection), so the exact
# ibrun line is right there to read and edit.
#
# scf mode runs one pw.x per case. relax mode runs an iterative vc-relax: it
# re-runs each case, feeding the relaxed structure back via update_structure.py
# (every pass is kept as scf.in.iter<N> / scf.out.iter<N>, amendment 2026-10-05),
# until the structure is self-consistent or --max-iter is reached.
#
#   ./make_jobscript.sh --mode relax --account PHY24018 \
#       --ibrun "ibrun pw.x -npool 8" \
#       --dirs "ecut_relax_sweep/* kpt_relax_sweep/*" --out jobscript
#
# IMPORTANT: the generated script uses `module reset` (not `module purge`) so the
# TACC module that provides `ibrun` stays on PATH.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

jobname="qe_conv"
nodes=1
ntasks=128
queue="normal"
time="12:00:00"
account="PHY24018"
modules="intel/19.1.1 impi/19.0.9 qe"
ibrun="ibrun pw.x"
mode="scf"
dirs=""
maxiter=5
cell_thr=0.01
angle_thr=0.05
pos_thr=0.01
scripts="$HERE"
# QE temp/outdir root on $SCRATCH, unique per job and per case (kept literal so
# $SCRATCH and $SLURM_JOB_ID expand inside the job, not when generating).
scratch='$SCRATCH/qe_tmp/$SLURM_JOB_ID'
out="jobscript"

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --jobname)   jobname="$2";   shift 2;;
        --nodes)     nodes="$2";     shift 2;;
        --ntasks)    ntasks="$2";    shift 2;;
        --queue)     queue="$2";     shift 2;;
        --time)      time="$2";      shift 2;;
        --account)   account="$2";   shift 2;;
        --modules)   modules="$2";   shift 2;;
        --ibrun)     ibrun="$2";     shift 2;;
        --mode)      mode="$2";      shift 2;;
        --dirs)      dirs="$2";      shift 2;;
        --max-iter)  maxiter="$2";   shift 2;;
        --cell-thr)  cell_thr="$2";  shift 2;;
        --angle-thr) angle_thr="$2"; shift 2;;
        --pos-thr)   pos_thr="$2";   shift 2;;
        --scripts)   scripts="$2";   shift 2;;
        --scratch)   scratch="$2";   shift 2;;
        --out)       out="$2";       shift 2;;
        -h|--help)   usage 0;;
        *) echo "unknown argument: $1" >&2; usage 1;;
    esac
done

if [[ "$mode" != "scf" && "$mode" != "relax" ]]; then
    echo "--mode must be 'scf' or 'relax'" >&2; exit 1
fi
# default directory globs match the generators' default output dirs
if [[ -z "$dirs" ]]; then
    [[ "$mode" == "relax" ]] && dirs="ecut_relax_sweep/* kpt_relax_sweep/*" \
                             || dirs="ecut_sweep/* kpt_sweep/*"
fi

# --- header (SBATCH + environment), substituted at generation time ----------
cat > "$out" <<EOF
#!/bin/bash
#SBATCH -J $jobname
#SBATCH -o ${jobname}_%j.out
#SBATCH -e ${jobname}_%j.err
#SBATCH -N $nodes
#SBATCH -n $ntasks
#SBATCH -p $queue
#SBATCH -t $time
#SBATCH -A $account

# use 'module reset' (NOT purge) so ibrun stays on PATH
module reset
module load $modules
export OMP_NUM_THREADS=1

QE_SCRIPTS="$scripts"
# QE writes wavefunctions/charge-density here (heavy I/O on \$SCRATCH); the
# scf.in/scf.out you keep stay in \$WORK alongside this script.
SCRATCH_ROOT="$scratch"
EOF

# --- loop body: literal ibrun, runtime variables kept literal with \$ -------
if [[ "$mode" == "scf" ]]; then
cat >> "$out" <<EOF

for d in $dirs; do
    [ -f "\$d/scf.in" ] || continue
    echo "=== \$d ==="
    tmp="\$SCRATCH_ROOT/\$d"; mkdir -p "\$tmp"
    ( cd "\$d"; export ESPRESSO_TMPDIR="\$tmp"; $ibrun < scf.in > scf.out )
done
echo "all cases done."
EOF
else
cat >> "$out" <<EOF

for d in $dirs; do
    [ -f "\$d/scf.in" ] || continue
    echo "=== \$d ==="
    tmp="\$SCRATCH_ROOT/\$d"; mkdir -p "\$tmp"
    ( cd "\$d"
      export ESPRESSO_TMPDIR="\$tmp"
      for i in \$(seq 1 $maxiter); do
          echo "  vc-relax iteration \$i"
          $ibrun < scf.in > scf.out
          cp scf.in scf.in.iter\$i; cp scf.out scf.out.iter\$i   # keep every pass
          python3 "\$QE_SCRIPTS/update_structure.py" scf.in scf.out --iter \$i \\
              --cell-thr $cell_thr --angle-thr $angle_thr --pos-thr $pos_thr
          rc=\$?
          [ \$rc -eq 0 ] && { echo "  converged after \$i iteration(s)"; break; }
          [ \$rc -eq 2 ] && { echo "  run did not finish — stopping this case"; break; }
          # rc==1: structure updated, run again
      done )
done
echo "all cases done."
EOF
fi

chmod +x "$out"
echo "wrote $out  (mode=$mode, dirs: $dirs)"
