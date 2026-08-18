#!/usr/bin/env bash
# data_parser.sh — Parse VASP results from POSCAR_scaled_* directories.
#
# Usage:
#   bash data_parser.sh [options]
#
# Options:
#   -r, --relax   Treat as relaxation (check ionic convergence, use CONTCAR)
#   -x, --xml     Copy vasprun.xml files to output directory
#   -h, --help    Show this help and exit
#
# If no options are given the script runs interactively and asks both questions.
#
# Outputs (written to <FUNC>_<CALC>/ and archived as .tar.gz):
#   energies.dat            – lattice params + total energy per directory
#   electronic_band.dat     – band gap + Fermi energy per directory
#   combined_band_gaps.dat  – raw BAND_GAP output for each directory
#   magnetization.dat       – last magnetization block per directory
#   atom_counts.dat         – species and atom counts
#   convergence_summary.txt – pass/fail summary
#
# Run from within a FUNC/CALC/ directory that contains POSCAR_scaled_*/ subdirs.

set -u
shopt -s nullglob

RED="\033[0;31m"; GREEN="\033[0;32m"; CYAN="\033[0;36m"; RESET="\033[0m"

# ─── Defaults ─────────────────────────────────────────────────────────────────
IS_RELAX=-1   # -1 = not set yet
COPY_XML=-1

# ─── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -r|--relax) IS_RELAX=1;  shift ;;
        -x|--xml)   COPY_XML=1;  shift ;;
        -h|--help)
            sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'
            exit 0 ;;
        -*)
            echo -e "${RED}Unknown option: $1${RESET}" >&2
            exit 1 ;;
        *) break ;;
    esac
done

# ─── Interactive fallback for unset flags ──────────────────────────────────────
if [[ $IS_RELAX -eq -1 ]]; then
    read -rp "Do these calculations undergo relaxation? (y/n): " ans
    [[ $ans =~ ^[Yy]$ ]] && IS_RELAX=1 || IS_RELAX=0
fi

if [[ $COPY_XML -eq -1 ]]; then
    read -rp "Copy vasprun.xml files to summary folder? (y/n): " ans
    [[ $ans =~ ^[Yy]$ ]] && COPY_XML=1 || COPY_XML=0
fi

# ─── Print configuration ──────────────────────────────────────────────────────
if (( IS_RELAX )); then
    echo "Mode: Relaxation (ionic convergence, using CONTCAR for structure)"
else
    echo "Mode: Static (electronic convergence, using POSCAR for structure)"
fi
(( COPY_XML )) && echo "Option: vasprun.xml will be copied" || echo "Option: vasprun.xml will NOT be copied"

# ─── Check for POSCAR_scaled_* directories ────────────────────────────────────
scaled_dirs=(POSCAR_scaled_*/)
if [[ ${#scaled_dirs[@]} -eq 0 ]]; then
    echo -e "${RED}No POSCAR_scaled_* subdirectories found.${RESET}"
    exit 1
fi

FUNC="$(basename "$(dirname "$PWD")")"
CALC="$(basename "$PWD")"
echo -e "${CYAN}Detected FUNC=${FUNC}  CALC=${CALC}${RESET}\n"

# ─── Output directory setup ───────────────────────────────────────────────────
out_dir="${FUNC}_${CALC}"
mkdir -p "$out_dir"
(( COPY_XML )) && mkdir -p "$out_dir/vasprun"
out_abs="$(pwd)/$out_dir"

echo -e "Directory\tA(Å)\tB(Å)\tC(Å)\tEnergy(eV)"           > "$out_abs/energies.dat"
echo -e "Directory\tA(Å)\tB(Å)\tC(Å)\tGap_eV\tFermi_E_eV"   > "$out_abs/electronic_band.dat"
mag_file="$out_abs/magnetization.dat";   : > "$mag_file"
atom_counts_file="$out_abs/atom_counts.dat"; : > "$atom_counts_file"

# ─── Helper: compute lattice vector lengths from a POSCAR/CONTCAR ─────────────
get_lengths() {
    local f=$1
    if [[ ! -f $f ]]; then
        echo -e "${RED}ERROR: Structural file $f not found.${RESET}"
        a_len=b_len=c_len="NA"
        return 1
    fi

    local ax ay az bx by bz cx cy cz
    if ! { read -r ax ay az < <(awk 'NR==3{print $1,$2,$3}' "$f") &&
           read -r bx by bz < <(awk 'NR==4{print $1,$2,$3}' "$f") &&
           read -r cx cy cz < <(awk 'NR==5{print $1,$2,$3}' "$f"); }; then
        echo -e "${RED}ERROR: Could not read lattice vectors from $f.${RESET}"
        a_len=b_len=c_len="NA"
        return 1
    fi

    a_len=$(awk -v x=$ax -v y=$ay -v z=$az 'BEGIN{printf "%.4f", sqrt(x*x+y*y+z*z)}')
    b_len=$(awk -v x=$bx -v y=$by -v z=$bz 'BEGIN{printf "%.4f", sqrt(x*x+y*y+z*z)}')
    c_len=$(awk -v x=$cx -v y=$cy -v z=$cz 'BEGIN{printf "%.4f", sqrt(x*x+y*y+z*z)}')
}

# ─── Main loop ────────────────────────────────────────────────────────────────
total=0; converged=0; failed=()

for pos_dir in "${scaled_dirs[@]%/}"; do
    echo -e "\n${CYAN}Checking $pos_dir/ ...${RESET}"
    outcar="$pos_dir/OUTCAR"
    ((total++))

    if [[ ! -f $outcar ]]; then
        echo -e "${RED}No OUTCAR in $pos_dir – skipping.${RESET}"
        failed+=("$pos_dir (No OUTCAR)")
        continue
    fi

    # Convergence check
    if (( IS_RELAX )); then
        if grep -q "reached required accuracy" "$outcar"; then
            echo "Convergence: ionic relaxation successful"
        else
            echo -e "${RED}Ionic convergence not reached – skipping $pos_dir${RESET}"
            failed+=("$pos_dir (Ionic not converged)")
            continue
        fi
    else
        if grep -q "EDIFF is reached" "$outcar"; then
            echo "Convergence: electronic convergence reached"
        else
            echo -e "${RED}Electronic convergence not reached – skipping $pos_dir${RESET}"
            failed+=("$pos_dir (Electronic not converged)")
            continue
        fi
    fi

    # Choose structure file
    struct="$pos_dir/POSCAR"
    [[ $IS_RELAX -eq 1 && -f $pos_dir/CONTCAR ]] && struct="$pos_dir/CONTCAR"
    echo "Using structure file: $struct"

    # Atom species/counts
    symbols_line=$(awk 'NR==6{print}' "$struct")
    counts_line=$(awk  'NR==7{print}' "$struct")
    read -ra syms <<< "$symbols_line"
    read -ra cnts <<< "$counts_line"

    if ! grep -q "^# Directory" "$atom_counts_file"; then
        echo -ne "# Directory\t" >> "$atom_counts_file"
        for sym in "${syms[@]}"; do echo -ne "${sym}\t" >> "$atom_counts_file"; done
        echo "Total" >> "$atom_counts_file"
    fi
    total_atoms=0
    for num in "${cnts[@]}"; do ((total_atoms += num)); done
    echo -ne "$pos_dir\t" >> "$atom_counts_file"
    for num in "${cnts[@]}"; do echo -ne "$num\t" >> "$atom_counts_file"; done
    echo "$total_atoms" >> "$atom_counts_file"

    if ! grep -q "^# Species" "$mag_file"; then
        echo "# Species and atom index ranges (1-based):" >> "$mag_file"
        start=1
        for i in "${!syms[@]}"; do
            end=$((start + cnts[i] - 1))
            echo "# ${syms[i]}: ${start}-${end}" >> "$mag_file"
            start=$((end + 1))
        done
        echo -e "\n" >> "$mag_file"
    fi

    # Optionally copy vasprun.xml
    if (( COPY_XML )) && [[ -f $pos_dir/vasprun.xml ]]; then
        mkdir -p "$out_abs/vasprun/$pos_dir"
        cp "$pos_dir/vasprun.xml" "$out_abs/vasprun/$pos_dir/"
        echo "Copied vasprun.xml"
    fi

    # Extract total energy
    energy_line=$(grep -E "free  energy" "$outcar" | tail -1)
    if [[ $energy_line =~ TOTEN[[:space:]]*=[[:space:]]*([+-]?[0-9]+\.?[0-9]*) ]]; then
        energy=${BASH_REMATCH[1]}
        echo "Energy: $energy eV"
    else
        echo -e "${RED}Energy extraction failed for $pos_dir – skipping.${RESET}"
        failed+=("$pos_dir (Energy extraction failed)")
        continue
    fi

    get_lengths "$struct" || continue
    echo -e "$pos_dir\t$a_len\t$b_len\t$c_len\t$energy" >> "$out_abs/energies.dat"
    ((converged++))

    # Extract magnetization (last block)
    mag_block=$(awk '
        /magnetization \(x\)/ { found=1; buf=""; getline; getline; next }
        found && /^$/ { if (buf) last_buf=buf; buf=""; found=0; next }
        found { buf = buf $0 ORS }
        END { if (buf) print buf; else if (last_buf) print last_buf }
    ' "$outcar")

    if [[ -n $mag_block ]]; then
        { echo "Directory: $pos_dir"
          echo "Lattice: A=${a_len} B=${b_len} C=${c_len}"
          echo "$mag_block"; echo; } >> "$mag_file"
    fi

    # Band structure / Fermi energy via vaspkit
    gap_val="NA"; fermi_val="NA"
    if command -v vaspkit &>/dev/null && [[ -f "$pos_dir/EIGENVAL" ]]; then
        pushd "$pos_dir" >/dev/null || continue

        echo -e "303" | vaspkit >/dev/null 2>&1
        if [[ -f KPATH.in ]]; then
            [[ -f KPOINTS ]] && mv KPOINTS KPOINTS.tmp
            mv KPATH.in KPOINTS
            echo -e "211" | vaspkit >/dev/null 2>&1
            mv KPOINTS KPATH.in
            [[ -f KPOINTS.tmp ]] && mv KPOINTS.tmp KPOINTS

            if [[ -f BAND_GAP ]]; then
                gap_val=$(awk  '/Band Gap \(eV\):/{print $6; exit}'   BAND_GAP 2>/dev/null || echo "NA")
                fermi_val=$(awk '/Fermi Energy \(eV\):/{print $6; exit}' BAND_GAP 2>/dev/null || echo "NA")
                [[ $gap_val   ]] || gap_val="NA"
                [[ $fermi_val ]] || fermi_val="NA"
                { echo "=== $pos_dir ==="; cat BAND_GAP; echo; } >> "$out_abs/combined_band_gaps.dat"
                echo "Band gap: ${gap_val} eV  Fermi: ${fermi_val} eV"
            fi
        fi

        popd >/dev/null || exit
    else
        echo "Skipping band analysis (vaspkit or EIGENVAL not available)"
    fi

    echo -e "$pos_dir\t$a_len\t$b_len\t$c_len\t$gap_val\t$fermi_val" >> "$out_abs/electronic_band.dat"
done

# ─── Convergence summary ──────────────────────────────────────────────────────
summary="$out_abs/convergence_summary.txt"
{
    echo "Convergence summary  ($FUNC / $CALC)"
    echo "Generated: $(date)"
    echo
    printf "%-10s %10s %10s\n" "Total" "Converged" "Failed"
    printf "%-10d %10d %10d\n" $total $converged $((total - converged))
    if (( ${#failed[@]} > 0 )); then
        echo -e "\n--- Unconverged / Failed ---"
        printf '  • %s\n' "${failed[@]}"
    fi
} | tee "$summary"

echo -e "${GREEN}\n✓ Finished gathering results for ${FUNC}/${CALC}${RESET}"
echo -e "   → Energy         : ${CYAN}$out_abs/energies.dat${RESET}"
echo -e "   → Electronic band: ${CYAN}$out_abs/electronic_band.dat${RESET}"
echo -e "   → Band gaps      : ${CYAN}$out_abs/combined_band_gaps.dat${RESET}"
echo -e "   → Magnetization  : ${CYAN}$mag_file${RESET}"
echo -e "   → Atom counts    : ${CYAN}$atom_counts_file${RESET}"
echo -e "   → Summary        : ${CYAN}$summary${RESET}"
(( COPY_XML )) && echo -e "   → vasprun.xml    : ${CYAN}$out_abs/vasprun/${RESET}"

# Archive
if tar -zcf "${out_abs}.tar.gz" -C "$(dirname "$out_abs")" "$(basename "$out_abs")"; then
    echo -e "   Archived         : ${CYAN}${out_abs}.tar.gz${RESET}"
else
    echo -e "${RED}   Archive creation failed${RESET}"
fi

shopt -u nullglob
exit 0
