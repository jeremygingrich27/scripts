#!/usr/bin/env bash
# loop_over_inplane_lattice_constants.sh
# Pick a directory of POSCAR_scaled*/ runs, then for each integer N you give,
# copy that set into generated_dirs/N_<dir>/ and apply scale factors N N 1.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANGER_LOOP="${SCRIPT_DIR}/loop_scale_factor_changer.sh"

usage() {
    cat <<USAGE
Usage: $(basename "$0")

Interactive. Lists subdirectories, asks you to pick one and to enter a
space-separated list of in-plane scale numbers; for each number N it creates
generated_dirs/N_<dir>/ (copying the POSCAR_scaled*/ inputs) and runs the
scale-factor changer with N N 1.

  -h, --help   show this help and exit
USAGE
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }

og_dir="$PWD"

mapfile -t dirs < <(for d in */; do [[ -d "$d" ]] && echo "${d%/}"; done)
(( ${#dirs[@]} > 0 )) || { echo "ERROR: no subdirectories here" >&2; exit 1; }

echo "📁 Select a directory:"
for i in "${!dirs[@]}"; do printf "  [%d] %s\n" "$((i+1))" "${dirs[i]}"; done
read -rp "Number: " choice
[[ "$choice" =~ ^[0-9]+$ ]] && (( choice>=1 && choice<=${#dirs[@]} )) || { echo "ERROR: invalid choice" >&2; exit 1; }
selected_dir="${dirs[$((choice-1))]}"
echo "✅ Selected: $selected_dir"

read -rp "Enter a space-separated sequence of numbers: " -a numbers
(( ${#numbers[@]} > 0 )) || { echo "ERROR: no numbers given" >&2; exit 1; }

container_dir="generated_dirs"
mkdir -p "$container_dir"
echo "📦 Output under: $container_dir"

for num in "${numbers[@]}"; do
    echo "➡️  $num"
    new_dir="${container_dir}/${num}_${selected_dir}"
    for sub in "$selected_dir"/POSCAR_scaled*/; do
        [[ -d "$sub" ]] || continue
        sub_base="$(basename "$sub")"
        mkdir -p "$new_dir/$sub_base"
        for file in CHGCAR INCAR KPOINTS POSCAR POTCAR; do
            [[ -f "$sub/$file" ]] && cp "$sub/$file" "$new_dir/$sub_base/"
        done
    done
    ( cd "$new_dir" && bash "$CHANGER_LOOP" "$num" "$num" 1 )
done
echo "✅ Done."
