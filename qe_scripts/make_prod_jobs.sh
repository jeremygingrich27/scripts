#!/bin/bash
# make_prod_jobs.sh — split a deposition tree into multi-node SLURM jobs that
# run several pw.x cases at once inside one allocation.
#
# make_jobscript.sh runs one ibrun at a time, so on a multi-node allocation all
# but one node idles. This writes jobs that launch one pw.x per node with
# `ibrun -n <tasks> -o <offset>`, the TACC way to pack independent MPI runs into
# a single job, and processes each job's case list in waves of <nodes>.
#
#   ./make_prod_jobs.sh --root prod/pbesol --jobs 10 --nodes 3 --time 48:00:00
#
# Writes <root>/jobs/<name>_NN.slurm and <root>/joblists/<name>_NN.list, then
# prints the sbatch commands. It submits nothing.
#
# Case discovery: directories <root>/<element>/<spin>/<h*>/<xy_*> holding an
# scf.in. The list is sorted, so nospin cases group together and heights group
# within them, keeping each wave's members similar in cost (a wave takes as long
# as its slowest member).
#
# Restartable: a case whose scf.out already contains "JOB DONE" is skipped, so a
# resubmitted job resumes where it stopped. An scf.out from an unfinished run is
# archived with a timestamp, never deleted.
set -euo pipefail

root=""
jobs=10
nodes=3
tasks=128
npool=4
queue="normal"
time="48:00:00"
account="PHY24018"
modules="intel/19.1.1 impi/19.0.9 qe"
name=""

usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)     root="$2";     shift 2;;
        --jobs)     jobs="$2";     shift 2;;
        --nodes)    nodes="$2";    shift 2;;
        --tasks)    tasks="$2";    shift 2;;
        --npool)    npool="$2";    shift 2;;
        --queue)    queue="$2";    shift 2;;
        --time)     time="$2";     shift 2;;
        --account)  account="$2";  shift 2;;
        --modules)  modules="$2";  shift 2;;
        --name)     name="$2";     shift 2;;
        -h|--help)  usage 0;;
        *) echo "unknown argument: $1" >&2; usage 1;;
    esac
done

[[ -n "$root" ]] || { echo "--root is required" >&2; exit 1; }
[[ -d "$root" ]] || { echo "no such directory: $root" >&2; exit 1; }
[[ -z "$name" ]] && name="$(basename "$root")"

# --- collect cases, sorted so similar ones land in the same wave -------------
mapfile -t cases < <(find "$root" -mindepth 4 -maxdepth 4 -type d -name 'xy_*' \
                     -exec test -f '{}/scf.in' ';' -print | sort)
ncases=${#cases[@]}
(( ncases > 0 )) || { echo "no cases found under $root" >&2; exit 1; }

mkdir -p "$root/jobs" "$root/joblists" "$root/logs"
per=$(( (ncases + jobs - 1) / jobs ))

echo "$ncases cases under $root"
echo "$jobs jobs x $nodes nodes, up to $per cases each, $tasks tasks per case"
echo

for (( j = 0; j < jobs; j++ )); do
    start=$(( j * per ))
    (( start < ncases )) || break
    tag=$(printf "%s_%02d" "$name" "$((j + 1))")
    list="$root/joblists/$tag.list"
    : > "$list"
    for (( k = start; k < start + per && k < ncases; k++ )); do
        echo "${cases[$k]}" >> "$list"
    done
    n_in_job=$(wc -l < "$list")

    cat > "$root/jobs/$tag.slurm" <<EOF
#!/bin/bash
#SBATCH -J $tag
#SBATCH -o $root/logs/${tag}_%j.out
#SBATCH -e $root/logs/${tag}_%j.err
#SBATCH -N $nodes
#SBATCH -n $(( nodes * tasks ))
#SBATCH -p $queue
#SBATCH -t $time
#SBATCH -A $account

# 'module reset' (NOT purge) so ibrun stays on PATH
module reset
module load $modules
export OMP_NUM_THREADS=1

cd "\$SLURM_SUBMIT_DIR"

LIST="$list"
TASKS=$tasks
WAVE=$nodes
SCRATCH_ROOT="\$SCRATCH/qe_prod/\$SLURM_JOB_ID"

mapfile -t CASES < "\$LIST"
echo "\${#CASES[@]} cases in \$LIST, $nodes at a time"

i=0
while (( i < \${#CASES[@]} )); do
    pids=()
    for (( s = 0; s < WAVE; s++ )); do
        d="\${CASES[\$((i + s))]:-}"
        [[ -n "\$d" ]] || continue
        if [[ -f "\$d/scf.out" ]] && grep -q "JOB DONE" "\$d/scf.out"; then
            echo "skip (already done): \$d"
            continue
        fi
        # never delete a previous run: archive it
        [[ -f "\$d/scf.out" ]] && mv "\$d/scf.out" "\$d/scf.out.\$(date +%Y%m%d_%H%M%S)"
        tmp="\$SCRATCH_ROOT/\$d"
        mkdir -p "\$tmp"
        echo "start (offset \$((s * TASKS))): \$d"
        (
            cd "\$d"
            export ESPRESSO_TMPDIR="\$tmp"
            ibrun -n \$TASKS -o \$((s * TASKS)) pw.x -npool $npool < scf.in > scf.out
        ) &
        pids+=(\$!)
    done
    (( \${#pids[@]} > 0 )) && wait "\${pids[@]}" || true
    i=\$(( i + WAVE ))
done
echo "chunk \$LIST complete"
EOF
    chmod +x "$root/jobs/$tag.slurm"
    printf "  %-28s %3d cases\n" "$tag" "$n_in_job"
done

echo
echo "submit with:"
for f in "$root"/jobs/"$name"_*.slurm; do echo "  sbatch $f"; done
