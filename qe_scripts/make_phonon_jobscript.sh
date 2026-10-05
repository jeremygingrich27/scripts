#!/bin/bash
# make_phonon_jobscript.sh — write a TACC SLURM jobscript that runs the whole
# final/ phonon workflow in one shot, inside a single allocation:
#
#   tight iterative vc-relax (relax.in, update_structure.py loop)
#     -> copy relaxed geometry into scf.in (apply_structure.py)
#     -> scf (scf.in)                        [saves the wavefunctions ph.x reads]
#     -> ph.x (ph.in)                        [DFPT phonons on the q-grid]
#     -> q2r.x (q2r.in)                      [real-space force constants]
#     -> matdyn.x (matdyn.in, if present)    [dispersion along the band path]
#
# Each step is guarded: a step runs only if the previous one reached JOB DONE, so
# a failed relax/scf/ph.x stops the chain instead of feeding garbage downstream.
# All steps share one ESPRESSO_TMPDIR (NOT purged between them) so the scf save
# is still there for ph.x. Build the inputs first with setup_phonon.sh.
#
#   ./make_phonon_jobscript.sh --account PHY24018 \
#       --pw "ibrun pw.x -npool 4 -pd .true." --ph "ibrun ph.x -npool 4"
#
# Launchers are written verbatim (like make_jobscript.sh). q2r.x/matdyn.x are
# cheap and run serial via --post (default "ibrun -n 1").
#
# IMPORTANT: uses `module reset` (not `module purge`) so ibrun stays on PATH.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

jobname="qe_phonon"
nodes=1
ntasks=128
queue="normal"
time="24:00:00"
account="PHY24018"
modules="intel/19.1.1 impi/19.0.9 qe"
pw="ibrun pw.x -npool 4 -pd .true."
ph="ibrun ph.x -npool 4"
post="ibrun -n 1"
dir="final"
maxiter=5
cell_thr=0.005
angle_thr=0.05
pos_thr=0.005
scripts="$HERE"
scratch='$SCRATCH/qe_tmp/$SLURM_JOB_ID'
out="jobscript.ph"

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
        --pw)        pw="$2";        shift 2;;
        --ph)        ph="$2";        shift 2;;
        --post)      post="$2";      shift 2;;
        --dir)       dir="$2";       shift 2;;
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

# --- header (SBATCH + environment) ------------------------------------------
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
DIR="$dir"
# one tmpdir shared by every step (NOT purged between them: ph.x reads the
# wavefunctions the scf saved here).
export ESPRESSO_TMPDIR="$scratch/\$DIR"
mkdir -p "\$ESPRESSO_TMPDIR"
EOF

# --- workflow body (runtime vars kept literal with \$) ----------------------
cat >> "$out" <<EOF

cd "\$DIR"

# 1. tight iterative vc-relax -------------------------------------------------
converged=0
for i in \$(seq 1 $maxiter); do
    echo "=== vc-relax iteration \$i ==="
    $pw < relax.in > relax.out
    python3 "\$QE_SCRIPTS/update_structure.py" relax.in relax.out --iter \$i \\
        --cell-thr $cell_thr --angle-thr $angle_thr --pos-thr $pos_thr
    rc=\$?
    [ \$rc -eq 0 ] && { converged=1; echo "  relax converged after \$i iter(s)"; break; }
    [ \$rc -eq 2 ] && { echo "  relax did not finish — aborting"; exit 1; }
done
[ \$converged -eq 1 ] || { echo "relax not converged in $maxiter iter — aborting"; exit 1; }

# 2. carry the relaxed geometry into the scf input ----------------------------
python3 "\$QE_SCRIPTS/apply_structure.py" relax.in scf.in

# 3. scf (saves the wavefunctions ph.x reads) ---------------------------------
echo "=== scf ==="
$pw < scf.in > scf.out
grep -q "JOB DONE" scf.out || { echo "scf failed — not running ph.x"; exit 1; }

# 4. phonons (DFPT) -----------------------------------------------------------
echo "=== ph.x ==="
$ph < ph.in > ph.out
grep -q "JOB DONE" ph.out || { echo "ph.x failed — stopping"; exit 1; }

# 5. real-space force constants -----------------------------------------------
echo "=== q2r.x ==="
$post q2r.x < q2r.in > q2r.out

# 6. dispersion along the band path (if matdyn.in was generated) --------------
if [ -f matdyn.in ]; then
    echo "=== matdyn.x ==="
    $post matdyn.x < matdyn.in > matdyn.out
fi
echo "phonon workflow complete."
EOF

chmod +x "$out"
echo "wrote $out  (dir=$dir, pw='$pw', ph='$ph')"
