#!/usr/bin/env python3
"""phonon_extractor.py — Extract Phonon Frequencies and Displacements from OUTCAR

Reads a VASP OUTCAR file and extracts all phonon mode frequencies and
displacement eigenvectors, writing them to two CSV files.

Output files
------------
- ``phonon_frequencies.csv``   – mode index and raw frequency line
- ``phonon_displacements.csv`` – transposed displacement matrix
  (rows = displacement components, columns = modes)

**phonon_frequencies.csv** schema::

    ModeIndex,FrequencyLine
    1,"  1 f  =  12.3 THz   77.3 2PiTHz  410.1 cm-1  ..."
    2,"  2 f/i=   4.5 THz   ..."   <- imaginary frequency (flagged)

**phonon_displacements.csv** schema::

    Atom_Displacement,Mode1,Mode2,...
    atom1_dx,0.001,-0.002,...
    atom1_dy,...

Usage
-----
::

    python phonon_extractor.py [--outcar OUTCAR] \\
        [--freq-output FILE] [--disp-output FILE]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Extract phonon frequencies and displacements from a VASP OUTCAR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--outcar",
        default="OUTCAR",
        metavar="FILE",
        help="Path to the VASP OUTCAR file (default: OUTCAR).",
    )
    p.add_argument(
        "--freq-output",
        default="phonon_frequencies.csv",
        metavar="FILE",
        help="Output CSV for frequencies (default: phonon_frequencies.csv).",
    )
    p.add_argument(
        "--disp-output",
        default="phonon_displacements.csv",
        metavar="FILE",
        help="Output CSV for displacements (default: phonon_displacements.csv).",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for phonon_extractor.py."""
    args = build_parser().parse_args()
    outcar_path = Path(args.outcar)

    if not outcar_path.exists():
        sys.exit(f"[FAIL] OUTCAR file not found: {outcar_path}")

    with outcar_path.open() as f:
        lines = f.readlines()

    # --- Determine number of atoms ---
    n_atoms: int | None = None
    for line in lines:
        if "NIONS" in line:
            match = re.search(r"NIONS\s*=\s*(\d+)", line)
            if match:
                n_atoms = int(match.group(1))
                break

    if n_atoms is None:
        sys.exit("[FAIL] Could not determine number of atoms from OUTCAR (NIONS not found).")

    mode_counter = 0
    disp_matrix: list[list[float]] = []
    imaginary_modes: list[int] = []

    # --- Extract frequencies and displacements ---
    with open(args.freq_output, "w", newline="") as freq_file:
        freq_writer = csv.writer(freq_file)
        freq_writer.writerow(["ModeIndex", "FrequencyLine"])

        i = 0
        while i < len(lines):
            line = lines[i]
            # Match lines like "  1 f  =" or "  2 f/i=" (imaginary)
            freq_match = re.match(r"\s*(\d+)\s+f/?i?\s*=", line)
            if freq_match:
                mode_counter += 1

                # Flag imaginary modes (contain "f/i")
                if "f/i" in line:
                    imaginary_modes.append(mode_counter)

                freq_writer.writerow([mode_counter, line.strip()])

                # Skip the "X Y Z dx dy dz" header line
                i += 2

                # Read n_atoms displacement lines
                mode_disp: list[float] = []
                for atom_idx in range(n_atoms):
                    if i >= len(lines):
                        print(f"[WARN] Mode {mode_counter}: unexpected end of file "
                              f"at atom {atom_idx + 1} — mode may be incomplete.")
                        mode_disp.extend([0.0, 0.0, 0.0])
                        continue
                    parts = lines[i].split()
                    # Validate column count before accessing displacement columns
                    if len(parts) < 6:
                        print(f"[WARN] Mode {mode_counter}, atom {atom_idx + 1}: "
                              f"expected >= 6 columns, got {len(parts)} — using zeros.")
                        mode_disp.extend([0.0, 0.0, 0.0])
                    else:
                        try:
                            dx, dy, dz = float(parts[3]), float(parts[4]), float(parts[5])
                            mode_disp.extend([dx, dy, dz])
                        except (ValueError, IndexError):
                            print(f"[WARN] Mode {mode_counter}, atom {atom_idx + 1}: "
                                  f"cannot parse displacements — using zeros.")
                            mode_disp.extend([0.0, 0.0, 0.0])
                    i += 1
                disp_matrix.append(mode_disp)
                continue
            i += 1

    # Report imaginary frequencies
    if imaginary_modes:
        print(f"[WARN] {len(imaginary_modes)} imaginary mode(s) detected: "
              f"{imaginary_modes}")

    if mode_counter == 0:
        sys.exit("[FAIL] No phonon modes found in OUTCAR.")

    # --- Build displacement component identifiers ---
    atom_disp_ids = [
        f"atom{atom_idx}_{comp}"
        for atom_idx in range(1, n_atoms + 1)
        for comp in ("dx", "dy", "dz")
    ]

    # --- Write transposed displacement matrix ---
    disp_matrix_T = list(map(list, zip(*disp_matrix)))
    with open(args.disp_output, "w", newline="") as disp_file:
        disp_writer = csv.writer(disp_file)
        header = ["Atom_Displacement"] + [f"Mode{m}" for m in range(1, mode_counter + 1)]
        disp_writer.writerow(header)
        for atom_id, row in zip(atom_disp_ids, disp_matrix_T):
            disp_writer.writerow([atom_id] + row)

    print(f"[OK] Extracted {mode_counter} phonon modes ({len(imaginary_modes)} imaginary).")
    print(f"[OK] Frequencies written to {args.freq_output}")
    print(f"[OK] Displacements written to {args.disp_output}")


if __name__ == "__main__":
    main()
