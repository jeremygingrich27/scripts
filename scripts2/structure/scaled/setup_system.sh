#!/usr/bin/env bash
# setup_system.sh
# Build a SYS/FUNC/CALC/POSCAR_scaled_*/ calculation tree from a POSCARs/ set,
# generating STRUCTURE_INFO and KPOINTS via vaspkit. Run where POSCARs/ exists.
# Produces:
#   SYS/FUNC/CALC/POSCAR_scaled_*/POSCAR
#   SYS/<POSCAR_SET>_POSCAR        (one copy of the reference POSCAR)
set -euo pipefail
shopt -s nullglob

usage() {
    cat <<USAGE
Usage: $(basename "$0") <SYSTEM> <CALC> <KPR> <KSCHEME> <FUNCTIONAL>

  SYSTEM      top-level project dir (e.g. SrTiO3)
  CALC        calculation subdir name (e.g. scf)
  KPR         k-point spacing for vaspkit option 102 (e.g. 0.04)
  KSCHEME     k-mesh scheme number (e.g. 2 = Monkhorst-Pack)
  FUNCTIONAL  functional label, becomes the FUNC dir (e.g. PBEsol+U)

Prompts interactively to pick the POSCAR set and POTCAR flavour(s).
Example: $(basename "$0") SrTiO3 scf 0.04 2 PBEsol+U
USAGE
}

# ────────────────────────────── 1. PARSE ARGS ─────────────────────────────
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { usage; exit 0; }
if [[ "$#" -ne 5 ]]; then
    usage >&2
    exit 1
fi

SYS="$1"        # e.g. SrTiO3  → will become the top‑level project dir
CALC="$2"       # e.g. scf     → sub‑dir inside <FUNC>/
KPR="$3"        # e.g. 0.04    → k‑point spacing for vaspkit option 102
KSCHEME="$4"    # e.g. 2       → Monkhorst, etc.
FUNC="$5"       # e.g. PBEsol+U

[[ "$KPR"     =~ ^[0-9]*\.?[0-9]+$ ]] || { echo "ERROR: KPR must be a number, got '$KPR'" >&2; exit 1; }
[[ "$KSCHEME" =~ ^[0-9]+$ ]]          || { echo "ERROR: KSCHEME must be an integer, got '$KSCHEME'" >&2; exit 1; }

# ────────────────────────────── 2. PICK POSCAR SET ────────────────────────
POSCAR_ROOT="POSCARs"
[[ -d $POSCAR_ROOT ]] || { echo "ERROR: '$POSCAR_ROOT' directory not found."; exit 1; }

CANDIDATES=()
for d in "$POSCAR_ROOT"/*/; do
    [[ -n $(find "$d" -maxdepth 1 -type f -name 'POSCAR*' -print -quit) ]] && \
    CANDIDATES+=("$(basename "$d")")
done

if ((${#CANDIDATES[@]} == 0)); then
    echo "ERROR: No non‑empty POSCAR sets in '$POSCAR_ROOT/'."
    exit 1
fi

echo "Available POSCAR sets:"
PS3=$'\n↳ Select a set by number (Ctrl‑C to abort): '
select POSCARDIR in "${CANDIDATES[@]}"; do
    [[ -n "${POSCARDIR:-}" ]] && break
done
echo

POSCAR_SOURCE="$POSCAR_ROOT/$POSCARDIR"
echo "▶ Using POSCAR set: $POSCARDIR"

# ────────────────────────────── 3. CHOOSE POTCAR ──────────────────────────
read -rp "Available POTCAR: LDA, PBE — choose (comma‑separated): " user_in
IFS=',' read -ra SELECTED_POTCAR <<<"$user_in"

VALID=(LDA PBE)
for p in "${SELECTED_POTCAR[@]}"; do
    [[ " ${VALID[*]} " =~ " $p " ]] || { echo "ERROR: invalid POTCAR '$p'"; exit 1; }
done

# ───────────────────── 4. BUILD <SYS>/<FUNC>/<CALC>/ TREE ─────────────────
TARGET_ROOT="$SYS/$FUNC/$CALC"
mkdir -p "$TARGET_ROOT"

# Keep one copy of the reference POSCAR at SYS/<set>_POSCAR (unchanged)
cp   "$POSCAR_SOURCE/POSCAR" "$SYS/${POSCARDIR}_POSCAR"

for poscar_file in "$POSCAR_SOURCE"/POSCAR_scaled_*; do
    fname=$(basename "$poscar_file")              # POSCAR_scaled_*
    [[ "$fname" == "POSCAR" || "$fname" == "scales.txt" ]] && continue

    calc_dir="$TARGET_ROOT/$fname"                # FINAL DESTINATION
    mkdir -p "$calc_dir"
    cp "$poscar_file" "$calc_dir/POSCAR"

    # Loop over POTCAR flavour(s) — no extra sub‑folder (overwrite if >1 choice)
    for potcar in "${SELECTED_POTCAR[@]}"; do
        # Update ~/.vaspkit to reference chosen pseudopotential
        sed "s/PSEUDO/$potcar/" ~/.vaspkitbase > ~/.vaspkit

        # (A) Structure summary  (vaspkit option 01 → 103)
        ( cd "$calc_dir" && echo -e "01\n103" | vaspkit | \
          awk '/Summary/,/^\+.*\+/' > STRUCTURE_INFO )

        # (B) Automatic Γ‑centred or Monkhorst K‑mesh  (option 102)
        ( cd "$calc_dir" && echo -e "102\n$KSCHEME\n$KPR" | vaspkit | \
          awk '/Summary/,/^\+.*\+/' >> STRUCTURE_INFO )

        rm -f "$calc_dir/INCAR"   # remove auto‑generated INCAR (if any)
    done
done

echo -e "\n🎉  Setup complete."
echo    "    Calculations written under:  $TARGET_ROOT/"

