"""energy_vs_structure.py — Energy vs. Lattice Structure Analysis

Discovers all paired (atom_counts.dat, energies.dat) files under a root
directory, sorts datasets by average a lattice constant, lets the user
select datasets interactively, and produces three PNG plots:

- ``energy_vs_ca_ratio.png``  – Energy vs. c/a ratio
- ``energy_vs_c.png``         – Energy vs. c lattice constant
- ``energy_vs_a.png``         – Energy vs. a lattice constant

Usage
-----
::

    python energy_vs_structure.py [--root DIR] [--atoms-per-fu N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

try:
    from scipy.signal import find_peaks
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from data_processing import parse_energy_data
from file_utils import read_atom_counts, find_paired_files


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def ask_limits(name: str) -> list[float] | None:
    """Prompt the user for axis limits.

    Args:
        name: Axis identifier, e.g. ``'x'`` or ``'y'``.

    Returns:
        ``[min, max]`` on success, ``None`` if blank or invalid.
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


def get_average_a_lattice(fpath: Path) -> float:
    """Compute the mean in-plane lattice constant from energies.dat.

    Used to sort datasets by average a so they are presented in a
    physically meaningful order.

    Args:
        fpath: Path to energies.dat.

    Returns:
        Mean of (a + b) / 2 across all rows, or 0.0 if no data found.
    """
    a_values: list[float] = []
    try:
        with fpath.open() as f:
            for line in f:
                if not line.strip() or line.lower().startswith("directory"):
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    a, b = float(parts[1]), float(parts[2])
                    a_values.append((a + b) / 2)
                except ValueError:
                    continue
    except OSError:
        pass
    return float(np.mean(a_values)) if a_values else 0.0


def find_local_extrema(
    x: np.ndarray, y: np.ndarray
) -> tuple[list[int], list[int]]:
    """Find indices of local maxima and minima in a dataset.

    Uses scipy.signal.find_peaks if available, otherwise a simple
    three-point comparison.

    Args:
        x: x-values array (used only for length).
        y: y-values array.

    Returns:
        ``(peaks, troughs)`` — lists of integer indices.
    """
    if SCIPY_AVAILABLE:
        peaks, _ = find_peaks(y)
        troughs, _ = find_peaks(-y)
        return list(peaks), list(troughs)

    peaks: list[int] = []
    troughs: list[int] = []
    for i in range(1, len(y) - 1):
        if y[i] > y[i - 1] and y[i] > y[i + 1]:
            peaks.append(i)
        if y[i] < y[i - 1] and y[i] < y[i + 1]:
            troughs.append(i)
    return peaks, troughs


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    p = argparse.ArgumentParser(
        description="Plot energy vs. lattice structure parameters from VASP output.",
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

def load_all_datasets(
    root: Path,
) -> tuple[list[str] | None, dict[int, dict]]:
    """Discover and sort all datasets under root by average a lattice constant.

    Args:
        root: Root directory to search.

    Returns:
        ``(species_list, dataset_info)`` where ``dataset_info`` maps integer
        indices (sorted by avg_a) to dicts with keys:
        ``path``, ``atom_file``, ``energy_file``, ``species_counts``,
        ``total_atoms``, ``default_name``, ``avg_a``.
    """
    pairs = find_paired_files(root)
    if not pairs:
        sys.exit("[FAIL] No paired atom_counts.dat + energies.dat files found.")

    # Build a flat index from nested hierarchy
    temp: dict[int, dict] = {}
    species_list: list[str] | None = None

    for i, (atom_file, energy_file) in enumerate(pairs):
        path_str = str(atom_file.parent.relative_to(root))
        try:
            species, atom_data = read_atom_counts(atom_file)
            if species_list is None:
                species_list = species

            dir_name = atom_file.parent.name
            matching = next(
                (d for k, d in atom_data.items() if k == dir_name or k in str(atom_file.parent)),
                list(atom_data.values())[0] if atom_data else None,
            )
            if matching is None:
                print(f"[FAIL] No composition entry for {path_str}")
                continue

            avg_a = get_average_a_lattice(energy_file)
            temp[i] = {
                "path": path_str,
                "atom_file": atom_file,
                "energy_file": energy_file,
                "species_counts": matching["species_counts"],
                "total_atoms": matching["total_atoms"],
                "default_name": path_str,
                "avg_a": avg_a,
            }
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"[FAIL] Dataset {i} ({path_str}): {exc}")

    # Re-index sorted by increasing a lattice constant
    sorted_items = sorted(temp.items(), key=lambda kv: kv[1]["avg_a"])
    dataset_info = {new_idx: info for new_idx, (_, info) in enumerate(sorted_items)}
    return species_list, dataset_info


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for energy_vs_structure.py."""
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

    # --- Discover and list datasets ---
    species_list, dataset_info = load_all_datasets(root)
    if not dataset_info:
        sys.exit("[FAIL] No datasets loaded.")

    print(f"\n{'='*60}")
    print("INDEXED DATASETS (sorted by increasing a lattice constant)")
    print(f"{'='*60}")
    for new_idx, info in dataset_info.items():
        comp = ""
        if species_list:
            comp = ", ".join(
                f"{species_list[j]}: {info['species_counts'][j]}"
                for j in range(len(species_list))
            )
        print(f"  [{new_idx}] {info['path']}  (avg a = {info['avg_a']:.3f} A)")
        if comp:
            print(f"       Composition: {comp}  (Total: {info['total_atoms']})")
        print()

    # --- Dataset selection ---
    print(f"\n{'='*60}")
    print("DATASET SELECTION")
    print(f"{'='*60}")
    selection_input = input("Enter dataset indices to plot (space-separated): ").strip()
    if not selection_input:
        sys.exit("[FAIL] No datasets selected.")

    try:
        selected_indices = list(map(int, selection_input.split()))
    except ValueError:
        sys.exit("[FAIL] Invalid input — must be integers.")

    valid_indices = [i for i in selected_indices if i in dataset_info]
    if not valid_indices:
        sys.exit("[FAIL] No valid indices selected.")

    # --- Atoms per formula unit ---
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

    # --- Parse energy data ---
    print(f"\n{'='*60}")
    print("PROCESSING ENERGY DATA")
    print(f"{'='*60}")
    datasets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    datasets_c: dict[str, np.ndarray] = {}
    datasets_a: dict[str, np.ndarray] = {}

    for idx in valid_indices:
        info = dataset_info[idx]
        try:
            x, y, c_vals, a_vals, *_ = parse_energy_data(
                info["energy_file"], atoms_per_fu, info["total_atoms"]
            )
            if len(x) == 0:
                print(f"  [FAIL] No valid data points for {info['path']}")
                continue
            custom = input(f"  Label [{info['default_name']}]: ").strip()
            label = custom if custom else info["default_name"]
            datasets[label] = (x, y)
            datasets_c[label] = c_vals
            datasets_a[label] = a_vals
            print(f"  [OK] {label}: {len(x)} points, c/a {x.min():.3f}-{x.max():.3f}")
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f"  [FAIL] {info['path']}: {exc}")

    if not datasets:
        sys.exit("[FAIL] No valid datasets to plot.")

    # --- Global minima + energy reference ---
    print(f"\n{'='*60}")
    print("GLOBAL MINIMA ANALYSIS")
    print(f"{'='*60}")
    minima_info: dict[int, tuple] = {}
    for i, (label, (x, y)) in enumerate(datasets.items()):
        min_idx = int(np.argmin(y))
        minima_info[i] = (label, float(y[min_idx]), float(x[min_idx]))
        print(f"  [{i}] {label}: min at c/a={x[min_idx]:.3f}, E={y[min_idx]:.6f}")

    ref_choice = input("Select reference zero index or Enter for none: ").strip()
    reference_energy = 0.0
    if ref_choice:
        try:
            ref_idx = int(ref_choice)
            if 0 <= ref_idx < len(minima_info):
                reference_energy = minima_info[ref_idx][1]
                print(f"[OK] Using {minima_info[ref_idx][0]} as zero reference")
            else:
                print("[FAIL] Invalid reference index, no reference applied.")
        except ValueError:
            print("[FAIL] Invalid input, no reference applied.")

    offset_datasets = {label: (x, y - reference_energy) for label, (x, y) in datasets.items()}

    # --- Optional vertical spacing ---
    if input("Add vertical spacing between curves? (y/n): ").strip().lower() == "y":
        try:
            spacing_value = float(input("Enter spacing value in eV/f.u.: "))
            for i, label in enumerate(offset_datasets):
                x, y = offset_datasets[label]
                offset_datasets[label] = (x, y + i * spacing_value)
        except ValueError:
            print("Invalid spacing value, no spacing applied.")

    # --- Local extrema ---
    print(f"\n{'='*60}")
    print("LOCAL MAXIMA AND MINIMA")
    print(f"{'='*60}")
    for label, (x, y) in offset_datasets.items():
        peaks, troughs = find_local_extrema(x, y)
        print(f"\nDataset: {label}")
        for p in peaks:
            print(f"  Local max at c/a={x[p]:.3f}, E={y[p]:.6f}")
        for t in troughs:
            print(f"  Local min at c/a={x[t]:.3f}, E={y[t]:.6f}")
        if not peaks and not troughs:
            print("  No local extrema found")

    # --- Axis limits ---
    x_lims = ask_limits("x")
    y_lims = ask_limits("y")

    def _apply_limits(ax: plt.Axes) -> None:
        if x_lims:
            ax.set_xlim(x_lims)
        if y_lims:
            ax.set_ylim(y_lims)

    # --- Plot 1: Energy vs c/a ---
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, (x, y) in offset_datasets.items():
        ax.plot(x, y, "o-", label=label)
    ax.set_xlabel("c/a ratio")
    ax.set_ylabel("Energy per formula unit (eV/f.u.)")
    ax.set_title("Energy vs c/a ratio")
    ax.grid(True)
    ax.legend()
    _apply_limits(ax)
    fig.tight_layout()
    ca_out = root / "energy_vs_ca_ratio.png"
    fig.savefig(ca_out, dpi=300)
    plt.close(fig)

    # --- Plot 2: Energy vs c lattice constant ---
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, (x, y) in offset_datasets.items():
        if label in datasets_c:
            c_vals = datasets_c[label]
            c_sort = np.argsort(c_vals)
            ax.plot(c_vals[c_sort], y[c_sort], "o-", label=label)
    ax.set_xlabel("c lattice constant (Angstrom)")
    ax.set_ylabel("Energy per formula unit (eV/f.u.)")
    ax.set_title("Energy vs c lattice constant")
    ax.grid(True)
    ax.legend()
    # x_lims is for c/a; use separate limits for c-axis if user provides
    if y_lims:
        ax.set_ylim(y_lims)
    fig.tight_layout()
    c_out = root / "energy_vs_c.png"
    fig.savefig(c_out, dpi=300)
    plt.close(fig)

    # --- Plot 3: Energy vs a lattice constant ---
    fig, ax = plt.subplots(figsize=(8, 6))
    for label, (x, y) in offset_datasets.items():
        if label in datasets_a:
            a_vals = datasets_a[label]
            a_sort = np.argsort(a_vals)
            ax.plot(a_vals[a_sort], y[a_sort], "o-", label=label)
    ax.set_xlabel("a lattice constant (Angstrom)")
    ax.set_ylabel("Energy per formula unit (eV/f.u.)")
    ax.set_title("Energy vs a lattice constant")
    ax.grid(True)
    ax.legend()
    if y_lims:
        ax.set_ylim(y_lims)
    fig.tight_layout()
    a_out = root / "energy_vs_a.png"
    fig.savefig(a_out, dpi=300)
    plt.close(fig)

    print(f"\n[OK] Energy vs c/a         : {ca_out}")
    print(f"[OK] Energy vs c constant  : {c_out}")
    print(f"[OK] Energy vs a constant  : {a_out}")


if __name__ == "__main__":
    main()
