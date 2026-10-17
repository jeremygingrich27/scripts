#!/usr/bin/env bash
# phonon_downhill driver.  Each job ends by calling `downhill.sh next`, so the tree runs itself.
#
#   downhill.sh init   PHASE_ROOT START_DIR NAME_PREFIX
#       PHASE_ROOT   new folder for this tree (e.g. .../downhill/pbe_AFII_compressed)
#       START_DIR    relaxed start cell: POSCAR, KPOINTS, POTCAR, MAGMOM, and the phonopy
#                    disp-run INCAR (becomes INCAR.sp / INCAR.relax via make_incars.py)
#       NAME_PREFIX  job name start, e.g. tCuO-AFII-comp_pbe
#       Only sets up files; submits nothing.
#   downhill.sh next   ROUND_DIR      do / submit the next step of one round
#   downhill.sh status PHASE_ROOT     one line per round and scan
set -e
export DH=${DH:-$HOME/scripts/structure/phonon_downhill}
# phonopy 4's Rust thread pool cannot start under the LS6 login-node thread limit; one thread is plenty here
export RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1
source "$DH/downhill.conf"
[[ -n $VIRTUAL_ENV ]] || source "$VENV/bin/activate"

phase_root() { local d=$1; while [[ ! -d $d/inputs ]]; do d=$(dirname "$d"); done; echo "$d"; }

# job name: <prefix>_dh-<round>-<last direction>-<step>, e.g. tCuO-AFII-comp_pbe_dh-r1-SM4-Pnma-relax
job_name() {
    local node=$1 step=$2 root; root=$(phase_root "$node")
    local rel=${node#$root/} r dir
    r=$(echo "$rel" | grep -o 'round_[0-9]*' | tail -1); r=r${r#round_}
    dir=$(echo "$rel" | grep -o 'scan_[^/]*' | tail -1); dir=${dir#scan_}
    local tail="dh-$r${dir:+-$dir}-$step"
    echo "$(cat "$root/inputs/NAME_PREFIX")_${tail//_/-}"
}

# submit JOB_SCRIPT for NODE with WALL minutes, from inside NODE
submit() {
    local script=$1 node=$2 wall=$3 step=$4
    (( wall > MAX_WALL_H * 60 )) && wall=$(( MAX_WALL_H * 60 ))
    ( cd "$node" && sbatch -J "$(job_name "$node" "$step")" -t "$(printf "%02d:%02d:00" $((wall/60)) $((wall%60)))" \
        -N "$NODES" -n "$TASKS" -p "$QUEUE" -A "$ALLOC" -o "%x.%j.out" \
        --export=ALL,DH="$DH",NODE="$node",WALL_MIN="$wall" "$DH/$script" )
}

cmd_init() {
    local root=$1 start=$2
    mkdir -p "$root/inputs" "$root/round_0"
    cp "$start"/{POSCAR,KPOINTS,POTCAR,MAGMOM} "$root/inputs/"
    python3 "$DH/make_incars.py" "$start/INCAR" "$root/inputs"
    echo "$3" > "$root/inputs/NAME_PREFIX"
    cp "$start/POSCAR" "$root/round_0/POSCAR"
    echo "initialised $root; start it with: $DH/downhill.sh next $root/round_0"
}

cmd_next() {
    local node; node=$(cd "$1" && pwd)
    local root; root=$(phase_root "$node")
    local n=${node##*round_}
    [[ -f $node/STOPPED || -f $node/STABLE ]] && { echo "$node: finished ($(ls "$node" | grep -E '^(STOPPED|STABLE)$'))"; return; }

    # 1. RELAX (not in round 0: the start cell is already relaxed)
    if (( n > 0 )) && [[ ! -f $node/relax/DONE ]]; then
        submit job_relax.sh "$node" $(( RELAX_WALL_H * 60 )) relax; return
    fi

    # 2. SYMMETRY: findsym (moments along c) -> .cif record; phonons use the CONTCAR as is
    mkdir -p "$node/phonons"
    if (( n > 0 )) && [[ ! -f $node/symmetry/DONE ]]; then
        python3 "$DH/symmetry_step.py" "$node/relax/CONTCAR_final" "$root/inputs/MAGMOM" "$node/symmetry" "$SYMPREC" \
            || { echo "symmetry step failed (see $node/symmetry)" > "$node/STOPPED"; return; }
    fi
    [[ -f $node/phonons/POSCAR ]] || cp "$node/$( (( n > 0 )) && echo relax/CONTCAR_final || echo POSCAR)" "$node/phonons/POSCAR"

    # 3. PHONONS
    [[ -f $node/phonons/FAILED ]] && return
    if [[ ! -f $node/phonons/phonopy_disp.yaml ]]; then
        "$DH/setup_phonons.sh" "$node/phonons" "$root/inputs" || { echo "phonopy setup failed" > "$node/STOPPED"; return; }
    fi
    local todo; todo=$(for d in "$node"/phonons/disp-*; do [[ -f $d/COMPLETED ]] || echo "$d"; done | wc -l)
    if (( todo > 0 )); then
        submit job_phonons.sh "$node" $(( todo * SP_MINUTES * 12 / 10 + 30 )) phonons; return
    fi

    # 4. FIND UNSTABLE MODES
    if [[ ! -f $node/phonons/SOFT_MODES ]]; then
        "$DH/analyse_phonons.sh" "$node/phonons" || { echo "phonon analysis failed" > "$node/STOPPED"; return; }
    fi
    if [[ $(cat "$node/phonons/SOFT_MODES") == STABLE* ]]; then
        cp "$node/phonons/SOFT_MODES" "$node/STABLE"; echo "$node: STABLE"; return
    fi
    if (( n >= MAX_ROUNDS )); then
        echo "unstable after $MAX_ROUNDS rounds (max rounds)" > "$node/STOPPED"; return
    fi

    # 5 + 6. one scan per inequivalent direction (each scan seeds its own next round)
    for p in "$node"/phonons/directions/*.npy; do
        local name; name=$(basename "$p" .npy)
        local scan=$node/scan_$name
        [[ -d $scan ]] && continue
        mkdir -p "$scan"
        cp "$p" "$scan/pattern.npy"
        cp "$node/phonons/POSCAR" "$scan/start.POSCAR"
        submit job_scan.sh "$scan" $(( SCAN_POINTS_PER_JOB * SP_MINUTES + 30 )) scan
    done
}

cmd_status() {
    find "$1" -maxdepth 40 -type d \( -name 'round_*' -o -name 'scan_*' \) | sort | while read -r d; do
        local state="running/queued"
        [[ -f $d/STABLE ]] && state="STABLE: $(cat "$d/STABLE")"
        [[ -f $d/STOPPED ]] && state="STOPPED: $(cat "$d/STOPPED")"
        [[ -f $d/scan.dat ]] && state="$state; $(($(wc -l < "$d/scan.dat") - 1)) points"
        ls -d "$d"/round_* > /dev/null 2>&1 && [[ $d == */scan_* ]] && state="minimum found -> $(cat "$d"/round_*/SOURCE)"
        echo "${d#$1/}: $state"
    done
}

case $1 in
    init)   shift; cmd_init "$@" ;;
    next)   shift; cmd_next "$@" ;;
    status) shift; cmd_status "$@" ;;
    *)      sed -n '2,14p' "$0"; exit 1 ;;
esac
