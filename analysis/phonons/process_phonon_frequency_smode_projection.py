#!/usr/bin/env python3
"""process_phonon_frequency_smode_projection.py — Phonon Mode Analysis

Correlates phonon mode frequencies with symmetry-mode (irrep) projections.
For each phonon mode, lists all irreducible representations (irreps) whose
projection value exceeds a configurable threshold.

Input files
-----------
- **frequencies CSV** — produced by ``phonon_extractor.py``::

    ModeIndex,FrequencyLine
    1,"  1 f  =  12.3 THz ..."

- **irreps CSV** — produced by ``smodes_projected_onto_phmodes.py``::

    ,Mode1,Mode2,...
    Irrep_A,0.95,0.01,...
    Irrep_B,0.01,0.88,...

Output
------
A plain-text ``.txt`` file with one block per phonon mode listing all
above-threshold irreps sorted by descending absolute projection value.

Usage
-----
::

    python process_phonon_frequency_smode_projection.py \\
        FREQ_FILE IRREP_FILE \\
        [--threshold T] [--header TEXT] [--output FILE] [--decimals N]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_frequency_file(freq_file: str) -> dict[int, str]:
    """Parse a frequency CSV and return a mapping from mode index to frequency line.

    Args:
        freq_file: Path to the frequencies CSV file.

    Returns:
        Dict mapping integer mode indices to raw frequency-line strings.

    Raises:
        FileNotFoundError: If *freq_file* does not exist.
        SystemExit: On missing required columns or parse errors.
    """
    if not Path(freq_file).exists():
        sys.exit(f"[FAIL] Frequency file not found: '{freq_file}'")

    frequencies: dict[int, str] = {}
    try:
        with open(freq_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mode_index = int(row["ModeIndex"])
                    frequencies[mode_index] = row["FrequencyLine"].strip()
                except KeyError as exc:
                    sys.exit(f"[FAIL] Expected column {exc} not found in frequency file.")
                except ValueError as exc:
                    print(f"[WARN] Cannot parse ModeIndex '{row.get('ModeIndex')}': {exc} — skipping.")
    except OSError as exc:
        sys.exit(f"[FAIL] Cannot read frequency file: {exc}")

    return frequencies


def parse_irrep_file(irrep_file: str) -> tuple[dict[str, list[float]], list[str]]:
    """Parse an irrep CSV and return the projection matrix.

    Args:
        irrep_file: Path to the irrep projection CSV file.

    Returns:
        ``(irrep_data, mode_columns)`` where ``irrep_data`` maps irrep-name
        strings to lists of projection values (one per mode column), and
        ``mode_columns`` is the ordered list of mode-column names.

    Raises:
        FileNotFoundError: If *irrep_file* does not exist.
        SystemExit: On parse errors.
    """
    if not Path(irrep_file).exists():
        sys.exit(f"[FAIL] Irrep file not found: '{irrep_file}'")

    irrep_data: dict[str, list[float]] = {}
    mode_columns: list[str] = []

    try:
        with open(irrep_file, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                sys.exit("[FAIL] Irrep file is empty.")
            mode_columns = [col for col in header[1:] if col.startswith("Mode")]

            for row in reader:
                if len(row) < len(header):
                    continue
                irrep_name = row[0].strip()
                if not irrep_name:
                    continue

                # Warn on duplicate irrep names (second occurrence would silently overwrite)
                if irrep_name in irrep_data:
                    print(f"[WARN] Duplicate irrep name '{irrep_name}' — overwriting previous entry.")

                values: list[float] = []
                for i, col in enumerate(header[1:], 1):
                    if col.startswith("Mode") and i < len(row):
                        try:
                            values.append(float(row[i]))
                        except ValueError:
                            values.append(0.0)
                    elif col.startswith("Mode"):
                        values.append(0.0)

                if values:
                    irrep_data[irrep_name] = values
    except OSError as exc:
        sys.exit(f"[FAIL] Cannot read irrep file: {exc}")

    return irrep_data, mode_columns


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def extract_mode_number(mode_name: str) -> int | None:
    """Extract the integer mode number from a column name like ``Mode42``.

    Args:
        mode_name: Column label string.

    Returns:
        Integer mode number, or ``None`` if not parseable.
    """
    match = re.search(r"Mode(\d+)", mode_name)
    return int(match.group(1)) if match else None


def write_output_file(
    frequencies: dict[int, str],
    irrep_data: dict[str, list[float]],
    mode_columns: list[str],
    threshold: float,
    output_file: str,
    header: str,
    decimals: int = 6,
) -> None:
    """Write the formatted analysis output file.

    Args:
        frequencies: Mode-index-to-frequency-line mapping.
        irrep_data: Irrep-name-to-values mapping.
        mode_columns: Ordered list of mode column names.
        threshold: Minimum absolute projection value to include in output.
        output_file: Path for the output text file.
        header: Header string for the output file.
        decimals: Number of decimal places for projection values (default: 6).

    Raises:
        SystemExit: If the output file cannot be written.
    """
    # Map mode numbers to their column indices in the irrep matrix
    mode_mapping: dict[int, int] = {}
    for i, col in enumerate(mode_columns):
        num = extract_mode_number(col)
        if num is not None:
            mode_mapping[num] = i

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"{header}\n")
            f.write("=" * len(header) + "\n\n")
            f.write(f"Threshold: {threshold}\n\n")

            for mode_idx in sorted(frequencies):
                if mode_idx not in mode_mapping:
                    continue
                col_idx = mode_mapping[mode_idx]

                f.write(f"Mode {mode_idx}:\n")
                f.write(f"{frequencies[mode_idx]}\n")
                f.write("-" * 60 + "\n")

                # Collect irreps above threshold, sorted by descending |value|
                above: list[tuple[str, float]] = [
                    (name, values[col_idx])
                    for name, values in irrep_data.items()
                    if col_idx < len(values) and abs(values[col_idx]) >= threshold
                ]
                above.sort(key=lambda kv: abs(kv[1]), reverse=True)

                if above:
                    for name, value in above:
                        f.write(f"{name:<60} {value:>{decimals + 6}.{decimals}f}\n")
                else:
                    f.write("No irreps above threshold\n")

                f.write("\n")
    except OSError as exc:
        sys.exit(f"[FAIL] Cannot write output file: {exc}")

    print(f"[OK] Output written to: {output_file}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Analyse phonon modes and irrep projections.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("freq_file", help="CSV file with phonon frequencies.")
    p.add_argument("irrep_file", help="CSV file with irrep matrix data.")
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        metavar="T",
        help="Minimum |projection| to include in output (prompted if omitted).",
    )
    p.add_argument(
        "--header",
        default=None,
        metavar="TEXT",
        help="Header string for the output file (prompted if omitted).",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Output text file (default: <freq_stem>_<irrep_stem>_analysis.txt).",
    )
    p.add_argument(
        "--decimals",
        type=int,
        default=6,
        metavar="N",
        help="Decimal places for projection values (default: 6).",
    )
    return p


def main() -> None:
    """Entry point for process_phonon_frequency_smode_projection.py."""
    args = build_parser().parse_args()

    # --- Parse inputs ---
    print("Reading frequency file...")
    frequencies = parse_frequency_file(args.freq_file)
    print(f"  Found {len(frequencies)} phonon modes.")

    print("Reading irrep file...")
    irrep_data, mode_columns = parse_irrep_file(args.irrep_file)
    print(f"  Found {len(irrep_data)} irreps and {len(mode_columns)} mode columns.")

    # --- Consistency check ---
    max_freq_mode = max(frequencies) if frequencies else 0
    if len(mode_columns) != max_freq_mode:
        print(f"[WARN] Mode column count ({len(mode_columns)}) != max mode index "
              f"({max_freq_mode}).")
        resp = input("Continue anyway? (y/n): ")
        if resp.lower() != "y":
            sys.exit(1)

    # --- Threshold ---
    if args.threshold is not None:
        threshold = args.threshold
        if threshold < 0:
            sys.exit("[FAIL] --threshold must be >= 0.")
    else:
        while True:
            try:
                raw = input("Enter threshold value (e.g. 0.001 or 1e-3): ").strip()
                threshold = float(raw)
                if threshold < 0:
                    print("Please enter a non-negative threshold.")
                    continue
                break
            except ValueError:
                print("Please enter a valid number.")

    # --- Header ---
    header = args.header
    if header is None:
        header = input("Enter header for output file: ").strip()
        if not header:
            header = "Phonon Mode Analysis Results"

    # --- Output filename ---
    if args.output:
        output_file = args.output
    else:
        freq_stem = Path(args.freq_file).stem
        irrep_stem = Path(args.irrep_file).stem
        output_file = f"{freq_stem}_{irrep_stem}_analysis.txt"

    # --- Validate decimals ---
    if args.decimals < 0:
        sys.exit("[FAIL] --decimals must be >= 0.")

    print(f"\nProcessing with threshold {threshold} ...")
    write_output_file(
        frequencies, irrep_data, mode_columns,
        threshold, output_file, header, args.decimals,
    )
    print("[OK] Analysis complete!")


if __name__ == "__main__":
    main()
