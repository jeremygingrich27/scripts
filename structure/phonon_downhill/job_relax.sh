#!/usr/bin/env bash
# Repeated relaxations of NODE (round_N) until one converges in its first ionic step.
#   relax/r01 starts from NODE/POSCAR, each later round from the previous CONTCAR.
#   A STOPCAR (LSTOP) ends VASP cleanly STOPCAR_MARGIN_MIN before the walltime.
source "$DH/job_common.sh"
root=$(phase_root)
mkdir -p "$NODE/relax"

while true; do
    last=$(ls -d "$NODE"/relax/r?? 2>/dev/null | tail -1)
    if [[ -n $last && ! -f $last/COMPLETED ]]; then
        cur=$last                                   # unfinished round: run it again
    else
        if [[ -n $last ]]; then n=$(( 10#${last##*/r} + 1 )); else n=1; fi
        (( n > MAX_RELAX_ROUNDS )) && stop_branch "relax: no convergence after $MAX_RELAX_ROUNDS rounds"
        cur=$(printf "%s/relax/r%02d" "$NODE" "$n")
        mkdir -p "$cur"
        if [[ -n $last ]]; then cp "$last/CONTCAR" "$cur/POSCAR"; else cp "$NODE/POSCAR" "$cur/POSCAR"; fi
        cp "$root/inputs/INCAR.relax" "$cur/INCAR"
        cp "$root/inputs/KPOINTS" "$root/inputs/POTCAR" "$cur/"
    fi
    cd "$cur"
    rm -f STOPCAR

    # clean stop before the walltime
    left=$(minutes_left)
    if (( left < STOPCAR_MARGIN_MIN + 30 )); then resubmit job_relax.sh; exit 0; fi
    ( sleep $(( (left - STOPCAR_MARGIN_MIN) * 60 )); echo "LSTOP = .TRUE." > STOPCAR ) > /dev/null 2>&1 &
    timer=$!
    stop_timer() { pkill -P $timer 2>/dev/null; kill $timer 2>/dev/null; }   # the sleep, then its shell
    run_vasp || { stop_timer; stop_branch "relax: VASP failed in $cur"; }
    stop_timer

    python3 "$DH/check_moments.py" . "$MIN_MOMENT" || stop_branch "relax: AFII moments lost in $cur"
    verdict=$(python3 "$DH/relax_check.py" . "$root/inputs/POSCAR" "$AB_TOL" | tee relax_check.log | tail -1)
    case $verdict in
        CONVERGED) cp CONTCAR "$NODE/relax/CONTCAR_final"; touch "$NODE/relax/DONE"; break ;;
        HALT*)     stop_branch "relax: ${verdict#HALT } ($cur)" ;;
        CONTINUE)  [[ -f STOPCAR ]] && { resubmit job_relax.sh; exit 0; } ;;
    esac
done

"$DH/downhill.sh" next "$NODE"
