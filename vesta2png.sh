#!/usr/bin/env bash
# vesta2png.sh — convert VESTA raster exports (.bmp.tif / .tif / .bmp) to
# content-trimmed PNGs next to the originals.
#
# usage: vesta2png.sh [-s N] [-m N] [-t] [-f] file [file ...]
#   -s N   scale output to N percent (e.g. -s 50)
#   -m N   keep an N-pixel white margin around the content (default 0)
#   -t     make the background transparent (flood fill from the corner,
#          so white specular highlights inside atoms are preserved)
#   -f     overwrite an existing .png (default: skip with a warning)
#
# examples:
#   vesta2png.sh La2CuO4.bmp.tif
#   vesta2png.sh -s 50 -m 20 *.bmp.tif
#   vesta2png.sh -t t-CuO_plane.bmp.tif

set -euo pipefail

scale="" margin=0 transparent=0 force=0
while getopts "s:m:tf" opt; do
  case $opt in
    s) scale=$OPTARG ;;
    m) margin=$OPTARG ;;
    t) transparent=1 ;;
    f) force=1 ;;
    *) exit 1 ;;
  esac
done
shift $((OPTIND-1))
[ $# -ge 1 ] || { grep '^#' "$0" | head -16 | sed 's/^# \{0,1\}//'; exit 1; }

for f in "$@"; do
  [ -f "$f" ] || { echo "skip (not found): $f" >&2; continue; }
  out=${f%.tif}; out=${out%.bmp}; out=${out%.TIF}; out=${out%.BMP}; out+=".png"
  if [ -e "$out" ] && [ $force -eq 0 ]; then
    echo "skip (exists, use -f): $out" >&2; continue
  fi

  args=( "$f" -trim +repage )
  [ "$margin" -gt 0 ] && args+=( -bordercolor white -border "$margin" )
  if [ $transparent -eq 1 ]; then
    # Flood-fill transparency from ALL FOUR corners, not just the top-left.
    # A structure that spans the frame cuts the white background into several
    # disconnected regions, and a single-corner fill leaves the others opaque
    # (this silently left 15-29% of the CuO6 octahedra exports white).
    # Whites *enclosed* by the structure -- atom specular highlights -- are
    # still preserved, because they touch no corner.
    # Rather than compute corner coordinates (which -draw will not expand),
    # bring each corner to 0,0 in turn with -flop/-flip. The four transforms
    # compose to the identity, so the image ends in its original orientation.
    args+=( -alpha set -fuzz 3% -fill none
            -draw 'matte 0,0 floodfill' -flop
            -draw 'matte 0,0 floodfill' -flip
            -draw 'matte 0,0 floodfill' -flop
            -draw 'matte 0,0 floodfill' -flip )
  fi
  [ -n "$scale" ] && args+=( -resize "${scale}%" )

  convert "${args[@]}" "$out"
  echo "$(identify -format '%f: %wx%h %b' "$out")   <- $f"
done
