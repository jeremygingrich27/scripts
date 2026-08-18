"""energy_vs_ca.py — Energy vs. C/A Ratio Analysis

Discovers all paired (atom_counts.dat, energies.dat) files under a root
directory, parses them into energy-per-formula-unit vs. c/a datasets,
lets the user select, splice, and label datasets interactively, then
produces two PNG plots and a JSON data file for later replotting.

Output files (written to the root directory)
--------------------------------------------
- ``combined_with_splicing.png`` – final (spliced) datasets
- ``combined_unspliced.png``     – original datasets before splicing
- ``plot_data.json``             – serialised datasets + metadata

JSON schema for plot_data.json
--------------------------------
::

    {
        "datasets": {
            "<label>": {"x": [float, ...], "y": [float, ...]}
        },
        "metadata": {
            "atoms_per_fu": int,
            "reference_energy": float,
            "xlabel": str,
            "ylabel": str,
            "title": str,
            "species_list": [str, ...],
            "dataset_compositions": {"<name>": [int, ...]},
            "x_lims": [float, float] | null,
            "y_lims": [float, float] | null
        }
    }

Usage
-----
::

    python energy_vs_ca.py [--root DIR] [--atoms-per-fu N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from data_processing import parse_energy_data, splice_datasets
from file_utils import read_atom_counts, find_paired_files, get_display_name


# ---------------------------------------------------------------------------
# Helper I/O functions
# ---------------------------------------------------------------------------

def ask_limits(name: str) -> list[float] | None:
    """Prompt for axis limits; return [min, max] or None.

    Args:
        name: Axis identifier shown in prompt, e.g. ``'x'`` or ``'y'``.

    Returns:
        Two-element float list on success, ``None`` if blank or unparseable.
    """
    raw = input(f"Enter {name}-axis limits (min max) or leave blank: ")
    try:
        vals = list(map(float, raw.split()))
        if len(vals) == 2:
            return vals
    except ValueError:
        pass
    if raw.strip():
        print(f"Invalid {name}-axis limits. Ignored.")
    return None


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for this script."""
    p = argparse.ArgumentParser(
        description="Plot energy per formula unit vs. c/a ratio from VASP output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="DIR",
        help="Root directory to search for paired data files (prompted if omitted).",
    )
    p.add_argument(
        "--atoms-per-fu",
        type=int,
        default=None,
        metavar="N",
        help="Atoms per formula unit (prompted if omitted).",
    )
    return p


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_dataset_info(
    pairs: list[tuple[Path, Path]],
) -> tuple[list[str] | None, dict[str, dict]]:
    """Load atomic composition data for all paired files.

    Args:
        pairs: List of ``(atom_counts_path, energies_path)`` tuples from
            :func:`file_utils.find_paired_files`.

    Returns:
        ``(species_list, dataset_info)`` where ``species_list`` is the list of
        element symbols and ``dataset_info`` maps display-name strings to dicts
        containing ``atom_file``, ``energy_file``, ``species_counts``,
        ``total_atoms``, and ``index``.
    """
    print(f"\n{'='*60}")
    print("LOADING ATOMIC COMPOSITION DATA")
    print(f"{'='*60}")

    dataset_info: dict[str, dict] = {}
    species_list: list[str] | None = None

    for i, (atom_file, energy_file) in enumerate(pairs):
        display_name = get_display_name(atom_file)
        try:
            species, atom_data = read_atom_counts(atom_file)
            if species_list is None:
                species_list = species

            # Use the first (usually only) entry if no exact directory match
            dir_name = atom_file.parent.name
            matching = next(
                (d for k, d in atom_data.items() if k == dir_name or k in str(atom_file.parent)),
                list(atom_data.values())[0] if atom_data else None,
            )
            if matching is None:
                print(f"[FAIL] Could not find composition entry for {display_name}")
                continue

            dataset_info[display_name] = {
                "atom_file": atom_file,
                "energy_file": energy_file,
                "species_counts": matching["species_counts"],
                "total_atoms": matching["total_atoms"],
                "index": i,
            }
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"[FAIL] Could not load composition for {display_name}: {exc}")

    return species_list, dataset_info


def load_energy_datasets(
    dataset_info: dict[str, dict],
    atoms_per_fu: int,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Parse energies.dat for every dataset and return (x, y) arrays.

    Args:
        dataset_info: Mapping from name to dataset metadata (from :func:`load_dataset_info`).
        atoms_per_fu: Atoms per formula unit.

    Returns:
        Mapping from dataset name to ``(c_over_a, energy_per_fu)`` numpy arrays.
    """
    print(f"\n{'='*60}")
    print("PROCESSING ENERGY DATA")
    print(f"{'='*60}")

    raw: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, info in dataset_info.items():
        total_atoms = info["total_atoms"]
        try:
            # parse_energy_data returns 5 values; we only need the first two here
            x, y, *_ = parse_energy_data(info["energy_file"], atoms_per_fu, total_atoms)
            if len(x) > 0:
                raw[name] = (x, y)
                print(f"  [OK] {name}: {len(x)} points, c/a {x.min():.3f}-{x.max():.3f}")
            else:
                print(f"  [FAIL] No valid data points in {name}")
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"  [FAIL] {name}: {exc}")
    return raw


# ---------------------------------------------------------------------------
# Dataset grouping / splicing
# ---------------------------------------------------------------------------

def select_groups(dataset_names: list[str]) -> list[tuple]:
    """Interactively collect dataset groups for plotting.

    Args:
        dataset_names: Ordered list of available dataset names.

    Returns:
        List of group tuples: ``('single', idx)`` or ``('splice', idx1, idx2)``.
    """
    print(f"\n{'='*60}")
    print("DATASET SELECTION AND GROUPING")
    print(f"{'='*60}")
    print("  * Single dataset  : one index, e.g. '0'")
    print("  * Splice two sets : two indices, e.g. '0 1'")
    print("  * Multiple groups : separated by semicolons, e.g. '0; 1 2; 3'")
    print("")

    groups_input = input("Enter dataset groups: ").strip()
    if not groups_input:
        print("No groups specified.")
        return []

    groups: list[tuple] = []
    for group_str in groups_input.split(";"):
        group_str = group_str.strip()
        try:
            indices = list(map(int, group_str.split()))
        except ValueError:
            print(f"[FAIL] Invalid group '{group_str}' — must be integers")
            continue

        if len(indices) == 1:
            groups.append(("single", indices[0]))
        elif len(indices) == 2:
            groups.append(("splice", indices[0], indices[1]))
        else:
            print(f"[FAIL] Group '{group_str}' has {len(indices)} indices — only 1 or 2 supported")

    return groups


def build_final_datasets(
    groups: list[tuple],
    dataset_names: list[str],
    raw_datasets: dict[str, tuple[np.ndarray, np.ndarray]],
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Apply user labels and optional splicing to produce final datasets.

    Args:
        groups: Group list from :func:`select_groups`.
        dataset_names: Ordered list of dataset names.
        raw_datasets: Mapping from name to ``(x, y)`` arrays.

    Returns:
        Mapping from user-supplied label to ``(x, y)`` arrays.
    """
    print(f"\n{'='*60}")
    print("DATASET LABELING AND SPLICING")
    print(f"{'='*60}")

    datasets: dict[str, tuple] = {}
    for group_num, group in enumerate(groups, 1):
        print(f"\nGroup {group_num}:")

        if group[0] == "single":
            idx = group[1]
            if not (0 <= idx < len(dataset_names)):
                print(f"  [FAIL] Invalid index {idx}")
                continue
            original = dataset_names[idx]
            if original not in raw_datasets:
                print(f"  [FAIL] No data for {original}")
                continue
            x, y = raw_datasets[original]
            print(f"  Dataset: {original}  ({len(x)} points, c/a {x.min():.3f}-{x.max():.3f})")
            label = input(f"  Label [{original}]: ").strip() or original
            datasets[label] = raw_datasets[original]
            print(f"  [OK] Added as: {label}")

        elif group[0] == "splice":
            idx1, idx2 = group[1], group[2]
            if not (0 <= idx1 < len(dataset_names) and 0 <= idx2 < len(dataset_names)):
                print(f"  [FAIL] Invalid indices {idx1}, {idx2}")
                continue
            n1, n2 = dataset_names[idx1], dataset_names[idx2]
            if n1 not in raw_datasets or n2 not in raw_datasets:
                print(f"  [FAIL] Missing data for {n1} or {n2}")
                continue
            x1, y1 = raw_datasets[n1]
            x2, y2 = raw_datasets[n2]
            print(f"  Splicing: {n1} + {n2}")
            default_label = f"{n1}+{n2}"
            label = input(f"  Label [{default_label}]: ").strip() or default_label
            print("  Dataset 1 kept for c/a <= splice point")
            print("  Dataset 2 kept for c/a >  splice point")
            try:
                splice_point = float(input("  Splice point: "))
                spliced = splice_datasets(raw_datasets[n1], raw_datasets[n2], splice_point)
                datasets[label] = spliced
                print(f"  [OK] Spliced at c/a = {splice_point}, added as: {label}")
            except ValueError:
                print("  [FAIL] Invalid splice point — skipping")

    return datasets


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def make_plots(
    offset_datasets: dict[str, tuple[np.ndarray, np.ndarray]],
    raw_datasets: dict[str, tuple[np.ndarray, np.ndarray]],
    original_names_used: list[str],
    reference_energy: float,
    x_lims: list[float] | None,
    y_lims: list[float] | None,
    root: Path,
) -> tuple[Path, Path]:
    """Generate and save the two energy plots.

    Args:
        offset_datasets: Final (spliced + shifted) datasets.
        raw_datasets: Original datasets before splicing.
        original_names_used: Names from raw_datasets to include in the unspliced plot.
        reference_energy: Energy offset applied to all y values.
        x_lims: Optional x-axis limits.
        y_lims: Optional y-axis limits.
        root: Directory in which output files are saved.

    Returns:
        Paths to the two saved PNG files.
    """
    def _apply_limits(ax: plt.Axes) -> None:
        if x_lims:
            ax.set_xlim(x_lims)
        if y_lims:
            ax.set_ylim(y_lims)

    # Plot 1: spliced datasets
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, (x, y) in offset_datasets.items():
        ax.plot(x, y, "o-", label=label)
    ax.set_xlabel("c/a ratio")
    ax.set_ylabel("Energy per formula unit (eV/f.u.)")
    ax.set_title("Energy vs c/a - With Splicing")
    ax.grid(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(offset_datasets), 3))
    _apply_limits(ax)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.15)
    combined_out = root / "combined_with_splicing.png"
    fig.savefig(combined_out, dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Plot 2: unspliced original datasets
    fig, ax = plt.subplots(figsize=(8, 6))
    for name in original_names_used:
        if name in raw_datasets:
            x, y = raw_datasets[name]
            ax.plot(x, y - reference_energy, "o-", label=name)
    ax.set_xlabel("c/a ratio")
    ax.set_ylabel("Energy per formula unit (eV/f.u.)")
    ax.set_title("Energy vs c/a - Original Datasets")
    ax.grid(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(original_names_used), 3))
    _apply_limits(ax)
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.15)
    unspliced_out = root / "combined_unspliced.png"
    fig.savefig(unspliced_out, dpi=300, bbox_inches="tight")
    plt.close(fig)

    return combined_out, unspliced_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for energy_vs_ca.py."""
    args = build_parser().parse_args()

    # --- Root directory ---
    if args.root is not None:
        root = args.root.expanduser()
        if not root.is_dir():
            sys.exit(f"[FAIL] '{root}' is not a valid directory.")
    else:
        root = Path(input("Root directory: ").strip()).expanduser()
        if not root.is_dir():
            sys.exit(f"[FAIL] '{root}' is not a valid directory.")

    # --- Discover paired files ---
    pairs = find_paired_files(root)
    if not pairs:
        sys.exit("[FAIL] No paired atom_counts.dat + energies.dat files found.")

    print(f"\n{'='*60}")
    print(f"FOUND {len(pairs)} PAIRED DATASETS")
    print(f"{'='*60}")
    for i, (af, _) in enumerate(pairs):
        print(f"  [{i}] {get_display_name(af)}")

    species_list, dataset_info = load_dataset_info(pairs)
    if not dataset_info:
        sys.exit("[FAIL] No datasets loaded.")

    # --- Show available datasets ---
    print(f"\n{'='*60}")
    print("AVAILABLE DATASETS")
    print(f"{'='*60}")
    dataset_names = list(dataset_info.keys())
    for i, name in enumerate(dataset_names):
        info = dataset_info[name]
        if species_list:
            comp = ", ".join(
                f"{species_list[j]}: {info['species_counts'][j]}"
                for j in range(len(species_list))
            )
            print(f"  [{i}] {name}  |  {comp}  (Total: {info['total_atoms']})")
        else:
            print(f"  [{i}] {name}")

    # --- atoms per formula unit ---
    if args.atoms_per_fu is not None:
        atoms_per_fu = args.atoms_per_fu
        if atoms_per_fu <= 0:
            sys.exit("[FAIL] --atoms-per-fu must be a positive integer.")
    else:
        print(f"\n{'='*60}")
        print("FORMULA UNIT DEFINITION")
        print(f"{'='*60}")
        try:
            atoms_per_fu = int(input("Enter number of atoms per formula unit: "))
            if atoms_per_fu <= 0:
                raise ValueError
        except ValueError:
            sys.exit("[FAIL] Invalid input. Must be a positive integer.")

    # --- Load energy data ---
    raw_datasets = load_energy_datasets(dataset_info, atoms_per_fu)
    if not raw_datasets:
        sys.exit("[FAIL] No datasets loaded.")

    # --- Select groups (interactive) ---
    groups = select_groups(dataset_names)
    if not groups:
        sys.exit("[FAIL] No groups specified.")

    datasets = build_final_datasets(groups, dataset_names, raw_datasets)
    if not datasets:
        sys.exit("[FAIL] No datasets to plot.")

    # --- Global minima + energy reference ---
    print(f"\n{'='*60}")
    print("GLOBAL MINIMA ANALYSIS")
    print(f"{'='*60}")
    minima_info: dict[int, tuple] = {}
    for i, (label, (x, y)) in enumerate(datasets.items()):
        min_idx = int(np.argmin(y))
        minima_info[i] = (label, float(y[min_idx]), float(x[min_idx]))
        print(f"  [{i}] {label}: min = {y[min_idx]:.6f} eV/f.u. at c/a = {x[min_idx]:.3f}")

    print(f"\n{'='*60}")
    print("ENERGY REFERENCE SELECTION")
    print(f"{'='*60}")
    print(f"  * Enter index [0-{len(minima_info)-1}] to set that minimum as zero")
    print("  * Press Enter to keep absolute energies")
    print("")
    ref_choice = input("Select reference zero point: ").strip()
    reference_energy = 0.0
    ref_idx: int | None = None
    if ref_choice:
        try:
            ref_idx = int(ref_choice)
            if 0 <= ref_idx < len(minima_info):
                reference_energy = minima_info[ref_idx][1]
                print(f"[OK] Using {minima_info[ref_idx][0]} minimum as zero reference")
                print(f"     (Subtracting {reference_energy:.6f} eV/f.u.)")
            else:
                print("[FAIL] Invalid index, using absolute energies")
                ref_idx = None
        except ValueError:
            print("[FAIL] Invalid input, using absolute energies")
    else:
        print("Using absolute energies (no reference shift)")

    offset_datasets = {label: (x, y - reference_energy) for label, (x, y) in datasets.items()}

    # --- Track original dataset names for the unspliced plot ---
    original_names_used: list[str] = []
    for group in groups:
        if group[0] == "single":
            idx = group[1]
            if 0 <= idx < len(dataset_names):
                name = dataset_names[idx]
                if name not in original_names_used:
                    original_names_used.append(name)
        elif group[0] == "splice":
            for idx in (group[1], group[2]):
                if 0 <= idx < len(dataset_names):
                    name = dataset_names[idx]
                    if name not in original_names_used:
                        original_names_used.append(name)

    # --- Axis limits ---
    print(f"\n{'='*60}")
    print("GENERATING PLOTS")
    print(f"{'='*60}")
    x_lims = ask_limits("x")
    y_lims = ask_limits("y")

    combined_out, unspliced_out = make_plots(
        offset_datasets, raw_datasets, original_names_used,
        reference_energy, x_lims, y_lims, root,
    )

    # --- Save JSON for replotting ---
    plot_data = {
        "datasets": {
            label: {"x": x.tolist(), "y": y.tolist()}
            for label, (x, y) in offset_datasets.items()
        },
        "metadata": {
            "atoms_per_fu": atoms_per_fu,
            "reference_energy": reference_energy,
            "xlabel": "c/a ratio",
            "ylabel": "Energy per formula unit (eV/f.u.)",
            "title": "Energy per formula unit vs c/a ratio",
            "species_list": species_list,
            "dataset_compositions": {
                name: info["species_counts"] for name, info in dataset_info.items()
            },
            "x_lims": x_lims,
            "y_lims": y_lims,
        },
    }
    data_file = root / "plot_data.json"
    with data_file.open("w") as f:
        json.dump(plot_data, f, indent=2)

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"[OK] Spliced combined plot  : {combined_out}")
    print(f"[OK] Unspliced combined plot: {unspliced_out}")
    print(f"[OK] Plot data saved        : {data_file}")
    print(f"     (Use replot_energy_ca.py to modify plot appearance)")
    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
