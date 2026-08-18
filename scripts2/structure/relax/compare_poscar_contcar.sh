#!/usr/bin/env bash
# compare_poscar_contcar.sh
# Compare POSCAR and CONTCAR in the current directory and print "true" if they
# match within a tolerance, "false" otherwise (intended for use in relaxation
# convergence loops). Tolerance is RELATIVE: |p-c| <= tol * max(1,|p|,|c|).
#
# Usage: compare_poscar_contcar.sh [tolerance]   (default tolerance: 1e-8)
set -uo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,7p' "$0" >&2
    exit 0
fi

export TOLERANCE="${1:-1e-8}"

if [[ ! -f POSCAR || ! -f CONTCAR ]]; then
    echo "false"
    exit 1
fi

# Fast path: byte-identical files are trivially "converged".
if diff -q POSCAR CONTCAR >/dev/null 2>&1; then
    echo "true"
    exit 0
fi

python3 - <<'PYEOF' 2>/dev/null || echo "false"
import os, sys

tol = float(os.environ.get("TOLERANCE", "1e-8"))

with open("POSCAR")  as f: p_lines = f.readlines()
with open("CONTCAR") as f: c_lines = f.readlines()

if len(p_lines) != len(c_lines):
    print("false"); sys.exit(0)

for i, (pl, cl) in enumerate(zip(p_lines, c_lines)):
    pl, cl = pl.strip(), cl.strip()
    if i == 0:                       # comment line — ignore
        continue
    if not pl and not cl:            # both blank
        continue
    if not pl or not cl:             # one blank, one not
        print("false"); sys.exit(0)
    try:
        pn = [float(x) for x in pl.split()]
        cn = [float(x) for x in cl.split()]
        if len(pn) != len(cn):
            print("false"); sys.exit(0)
        for a, b in zip(pn, cn):
            if abs(a - b) > tol * max(1.0, abs(a), abs(b)):
                print("false"); sys.exit(0)
    except ValueError:               # non-numeric line — compare exactly
        if pl != cl:
            print("false"); sys.exit(0)

print("true")
PYEOF
