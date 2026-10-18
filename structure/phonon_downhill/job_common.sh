# Shared by job_relax.sh, job_phonons.sh, job_scan.sh.  Sourced, not run.
# Needs in the environment (downhill.sh passes them with sbatch --export):
#   DH        this scripts folder
#   NODE      the round_N (or scan) folder the job works on
#   WALL_MIN  the walltime the job was given, in minutes

module reset > /dev/null 2>&1
export OMP_NUM_THREADS=1
source "$DH/downhill.conf"
source "$VENV/bin/activate"

JOB_START=$(date +%s)

# minutes left before the walltime
minutes_left() {
    echo $(( WALL_MIN - ($(date +%s) - JOB_START) / 60 ))
}

# phase root = the nearest parent holding inputs/
phase_root() {
    local d=$NODE
    while [[ ! -d $d/inputs ]]; do d=$(dirname "$d"); done
    echo "$d"
}

# run VASP in the current folder; COMPLETED on success; CHGCAR moved to $SCRATCH
run_vasp() {
    ibrun "$VASP" > vasp.log 2>&1
    local rc=$?
    if [[ -f CHGCAR ]]; then
        local dest=$SCRATCH_DIR/$SLURM_JOB_ID/${PWD#$(phase_root)/}
        mkdir -p "$dest" && mv CHGCAR "$dest/" && echo "$dest/CHGCAR" > CHGCAR.location
    fi
    (( rc == 0 )) && touch COMPLETED
    return $rc
}

# out of walltime: stop cleanly; `downhill.sh advance` (login node) submits the rest
# (TACC does not allow sbatch from a compute node)
out_of_time() {
    echo "out of walltime: stopping; run downhill.sh advance on a login node to continue"
}

walltime() { printf "%02d:%02d:00" $(( $1 / 60 )) $(( $1 % 60 )); }

# stop this branch for a human to look at
stop_branch() {
    echo "$*" > "$NODE/STOPPED"
    echo "STOPPED: $*"
    exit 0
}
