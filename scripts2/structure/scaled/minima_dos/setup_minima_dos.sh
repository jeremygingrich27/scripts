#!/usr/bin/env bash
# setup_minima_dos.sh
# Build a tree of scf/dos (optionally bands) VASP decks, one per structure
# listed in a minima table.
#
# Layout produced, per table row:
#   <OUT>/<label>/scf/    INCAR KPOINTS POSCAR POTCAR
#   <OUT>/<label>/dos/    INCAR KPOINTS POSCAR POTCAR
#   <OUT>/<label>/bands/  INCAR KPOINTS POSCAR POTCAR   (only if bands=yes)
#
# Inputs:
#   --table    TSV with a header row; needs columns 'label' and 'bands'
#   --poscars  dir holding POSCAR_<label>, one per row
#   --assets   dir holding {scf,dos,bands}/{INCAR,KPOINTS,POTCAR}
#
# The per-stage INCAR/KPOINTS/POTCAR are copied verbatim; only the POSCAR
# differs between structures. Jobscripts are written separately.
set -euo pipefail

TABLE="./minima_table.tsv"
POSCARS="./poscars"
ASSETS="./assets"
OUT="."
ASSUME_YES=0

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Options:
      --table FILE    minima table TSV        (default: ${TABLE})
      --poscars DIR   dir of POSCAR_<label>   (default: ${POSCARS})
      --assets DIR    dir of <stage>/ assets  (default: ${ASSETS})
      --out DIR       output root             (default: ${OUT})
  -y, --yes           overwrite existing structure dirs without prompting
  -h, --help          show this help and exit
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --table)   TABLE="${2:?--table needs a value}";     shift 2 ;;
        --poscars) POSCARS="${2:?--poscars needs a value}"; shift 2 ;;
        --assets)  ASSETS="${2:?--assets needs a value}";   shift 2 ;;
        --out)     OUT="${2:?--out needs a value}";         shift 2 ;;
        -y|--yes)  ASSUME_YES=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

need_file() { [[ -f "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }
need_dir()  { [[ -d "$1" ]] || { echo "ERROR: missing $2: $1" >&2; exit 1; }; }

need_file "$TABLE" "minima table"
need_dir  "$POSCARS" "POSCAR dir"
for stage in scf dos bands; do
    for f in INCAR KPOINTS POTCAR; do
        need_file "${ASSETS}/${stage}/${f}" "asset ${stage}/${f}"
    done
done

# ---- locate the 'label' and 'bands' columns in the header -------------------
read -r header < "$TABLE"
IFS=$'\t' read -r -a cols <<< "$header"
lab_i=-1; bands_i=-1
for i in "${!cols[@]}"; do
    [[ "${cols[i]}" == "label" ]] && lab_i=$i
    [[ "${cols[i]}" == "bands" ]] && bands_i=$i
done
(( lab_i >= 0 ))   || { echo "ERROR: table has no 'label' column" >&2; exit 1; }
(( bands_i >= 0 )) || { echo "ERROR: table has no 'bands' column" >&2; exit 1; }

# ---- build ------------------------------------------------------------------
n=0; nb=0
while IFS=$'\t' read -r -a f; do
    label="${f[lab_i]}"
    [[ "$label" == "label" || -z "$label" ]] && continue
    src_poscar="${POSCARS}/POSCAR_${label}"
    need_file "$src_poscar" "POSCAR for ${label}"

    dest="${OUT}/${label}"
    if [[ -d "$dest" && $ASSUME_YES -eq 0 ]]; then
        read -r -p "  ${dest} exists. Overwrite? [y/N] " ans
        [[ "$ans" =~ ^[Yy]$ ]] || { echo "  skipped ${label}"; continue; }
    fi

    stages=(scf dos)
    [[ "${f[bands_i]}" == "yes" ]] && { stages+=(bands); nb=$((nb+1)); }

    for stage in "${stages[@]}"; do
        mkdir -p "${dest}/${stage}"
        cp -p "${ASSETS}/${stage}/INCAR"   "${dest}/${stage}/INCAR"
        cp -p "${ASSETS}/${stage}/KPOINTS" "${dest}/${stage}/KPOINTS"
        cp -p "${ASSETS}/${stage}/POTCAR"  "${dest}/${stage}/POTCAR"
        cp    "$src_poscar"                "${dest}/${stage}/POSCAR"
    done
    n=$((n+1))
    printf '  %-18s %s\n' "$label" "${stages[*]}"
done < <(tail -n +2 "$TABLE")

echo
echo "Built ${n} structure(s) under ${OUT}; ${nb} include a bands/ stage."
