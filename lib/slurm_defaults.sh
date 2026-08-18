#!/usr/bin/env bash
# lib/slurm_defaults.sh
# Shared SLURM / VASP defaults + jobscript-header generator for the ~/scripts
# toolkit. Every job-generating script sources this file so the cluster defaults
# live in ONE place — change them here and they update everywhere.
#
# Usage (from another script):
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"
#
# Override any default for a single run by exporting it first, e.g.
#   VASP_QUEUE=development VASP_CORES=64 bash write_jobscript.sh
#
# ---------------------------------------------------------------------------
# Cluster defaults (TACC Lonestar6). ':=' means "set only if not already set",
# so an exported environment variable or a flag-set value always wins.
# ---------------------------------------------------------------------------
: "${VASP_ACCOUNT:=PHY24018}"
: "${VASP_QUEUE:=normal}"
: "${VASP_NODES:=1}"
: "${VASP_CORES:=128}"                       # one full LS6 node = 128 cores
: "${VASP_TIME:=48:00:00}"
: "${VASP_COMPILER_MODULES:=intel/19.1.1 impi/19.0.9}"
: "${VASP_MODULE:=vasp/6.3.0}"
: "${VASP_BIN:=vasp_std}"                     # ibrun launches this (no -np on TACC)

# ---------------------------------------------------------------------------
# vasp_slurm_header NAME NODES CORES QUEUE TIME ACCOUNT
# Prints a complete jobscript header: shebang, #SBATCH directives, module loads
# and OMP setting. Redirect it into your jobscript, e.g.
#   vasp_slurm_header "$NAME" "$NODES" "$CORES" "$QUEUE" "$TIME" "$ACCOUNT" > jobscript
# ---------------------------------------------------------------------------
vasp_slurm_header() {
    local name="$1" nodes="$2" cores="$3" queue="$4" time="$5" account="$6"
    cat <<HDR
#!/bin/bash
#SBATCH -J ${name}
#SBATCH -o ${name}_%j.out
#SBATCH -e ${name}_%j.err
#SBATCH -N ${nodes}
#SBATCH -n ${cores}
#SBATCH -p ${queue}
#SBATCH -t ${time}
#SBATCH -A ${account}

module purge
module load ${VASP_COMPILER_MODULES}
module load ${VASP_MODULE}
export OMP_NUM_THREADS=1
HDR
}

# ---------------------------------------------------------------------------
# die MESSAGE [EXIT_CODE]   — print an error to stderr and exit (default code 1)
# need_file PATH [LABEL]    — die unless PATH exists as a regular file
# need_cmd  NAME            — die unless NAME is on PATH
# confirm   PROMPT          — return 0 only if the user answers y/Y
# These give every script consistent, readable error handling.
# ---------------------------------------------------------------------------
die() { echo "ERROR: $1" >&2; exit "${2:-1}"; }

need_file() {
    [[ -f "$1" ]] || die "${2:-Required file} not found: $1"
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found on PATH: $1"
}

confirm() {
    local reply
    read -rp "$1 [y/N]: " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}
