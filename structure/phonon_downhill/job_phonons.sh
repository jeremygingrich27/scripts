#!/usr/bin/env bash
# Run every phonopy displacement of NODE/phonons that has no COMPLETED, then hand back to the driver.
source "$DH/job_common.sh"
ph=$NODE/phonons

for d in "$ph"/disp-*; do
    [[ -f $d/COMPLETED ]] && continue
    if (( $(minutes_left) < SP_MINUTES + 10 )); then resubmit job_phonons.sh; exit 0; fi
    echo "running $d"
    cd "$d"
    run_vasp || { touch "$ph/FAILED"; stop_branch "VASP failed in $d"; }
done

"$DH/downhill.sh" next "$NODE"
