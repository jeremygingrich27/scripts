#!/usr/bin/env bash
# directory_restructure.sh
# Migrate the old  POSCAR_scaled_*/FUNC/CALC/  layout to the new
# FUNC/CALC/POSCAR_scaled_*  layout. Run from the directory holding the old tree.
set -euo pipefail

usage() {
    cat <<USAGE
Usage: $(basename "$0") [options]

Moves POSCAR_scaled_*/FUNC/CALC/ -> FUNC/CALC/POSCAR_scaled_*.

Options:
  -n, --dry-run   show what would move without moving anything
  -v, --verbose   print each move
  -h, --help      show this help and exit

(The DRY_RUN=1 / VERBOSE=1 environment variables still work as fallbacks.)
USAGE
}

DRY_RUN=${DRY_RUN:-0}
VERBOSE=${VERBOSE:-0}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--dry-run) DRY_RUN=1; shift ;;
        -v|--verbose) VERBOSE=1; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage >&2; exit 1 ;;
    esac
done

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

