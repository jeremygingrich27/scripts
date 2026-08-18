#!/usr/bin/env bash
# Move  POSCAR_scaled_*/FUNC/CALC/  ➜  FUNC/CALC/POSCAR_scaled_*
# -----------------------------------------------------------------
# Usage:
#   bash directory_restructure.sh        # live run
#   DRY_RUN=1 bash directory_restructure.sh   # print what would move
#   VERBOSE=1 bash directory_restructure.sh  # chatty
# -----------------------------------------------------------------

set -euo pipefail

DRY_RUN=${DRY_RUN:-0}     # export DRY_RUN=1 for dry‑run
VERBOSE=${VERBOSE:-0}

say() { (( VERBOSE )) && echo -e "$*"; }

# ── collect every CALC dir in the old hierarchy ───────────────────────────
mapfile -t OLD_DIRS < <(
  find POSCAR_scaled_* -mindepth 2 -maxdepth 2 -type d | sort
)

if [[ ${#OLD_DIRS[@]} -eq 0 ]]; then
  echo "Nothing to move — tree already in new layout?"
  exit 0
fi

moved=0 skipped=0

# ── main loop ─────────────────────────────────────────────────────────────
for src in "${OLD_DIRS[@]}"; do
  # Split path:  POSCAR_scaled_xxx / FUNC / CALC
  poscar_root=${src%%/*}              # first component
  rest=${src#*/}                      # FUNC/CALC
  func=${rest%%/*}
  calc=${rest#*/}

  dest="$func/$calc/$poscar_root"

  if [[ -d $dest ]]; then
    say "⚠️   $dest exists — skip"
    (( skipped++ ))
    continue
  fi

  say "mv $src  →  $dest"
  if (( DRY_RUN == 0 )); then
    mkdir -p "$func/$calc"
    mv "$src" "$dest"
  fi
  (( moved++ ))

  # Remove empty dirs left behind
  rmdir -p --ignore-fail-on-non-empty "$(dirname "$src")" 2>/dev/null || true
done

echo "Moved   : $moved"
echo "Skipped : $skipped"
(( DRY_RUN )) && echo "(dry‑run only – nothing moved)"

