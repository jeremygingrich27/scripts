#!/usr/bin/env bash
# Downhill scan along one direction.  NODE here is the scan folder (scan_<irrep>_<group>),
# holding start.POSCAR and pattern.npy.  scan_status.py decides every step.
source "$DH/job_common.sh"
root=$(phase_root)
cd "$NODE"

while true; do
    action=$(python3 "$DH/scan_status.py" . "$STEP" "$NPAST" | tee -a scan_status.log | tail -1)
    set -- $action
    case $1 in
        NEXT)  pt=$(printf "u_%.3f" "$2") ;;
        CHECK) pt=$(printf "check_u_%.4f" "$2") ;;
        MIN)
            # the minimum seeds the next round, next to this scan
            r=$(basename "$(dirname "$NODE")"); r=${r#round_}
            child=$NODE/round_$(( r + 1 ))
            mkdir -p "$child"
            cp "$2/POSCAR" "$child/POSCAR"
            echo "from $2" > "$child/SOURCE"
            "$DH/downhill.sh" next "$child"
            exit 0 ;;
        NOMIN) stop_branch "scan: lowest energy at u = 0, not downhill" ;;
        HALT)  shift; stop_branch "scan: $*" ;;
        *)     stop_branch "scan: unexpected scan_status output '$action'" ;;
    esac

    if (( $(minutes_left) < SP_MINUTES + 10 )); then resubmit job_scan.sh; exit 0; fi
    mkdir -p "$pt"
    python3 "$DH/make_scan_point.py" start.POSCAR pattern.npy "$2" "$pt/POSCAR"
    cp "$root/inputs/INCAR.sp" "$pt/INCAR"
    cp "$root/inputs/KPOINTS" "$root/inputs/POTCAR" "$pt/"
    cd "$pt"
    run_vasp || stop_branch "scan: VASP failed in $pt"
    python3 "$DH/check_moments.py" . "$MIN_MOMENT" || touch MOMENTS_LOST
    cd "$NODE"
done
