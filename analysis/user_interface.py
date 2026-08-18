"""User Interface Module for Energy vs. C/A Analysis

Provides interactive prompts and input-handling helpers shared across
energy_vs_ca.py, energy_vs_structure.py, and related scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

from data_processing import splice_datasets


def ask_limits(name: str) -> list[float] | None:
    """Prompt the user for axis limits.

    Args:
        name: Axis name shown in the prompt, e.g. ``'x'`` or ``'y'``.

    Returns:
        ``[min, max]`` if the user entered two numbers, ``None`` otherwise.
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


def get_user_root_directory() -> Path:
    """Prompt the user for a root directory path.

    Returns:
        Resolved ``Path`` object for the root directory.

    Raises:
        SystemExit: If the path does not refer to an existing directory.
    """
    root = Path(input("Root directory: ").strip()).expanduser()
    if not root.is_dir():
        sys.exit(f"'{root}' is not a valid directory.")
    return root


def get_user_dataset_selection(dataset_names: list[str]) -> list[tuple]:
    """Prompt the user to select and group datasets for plotting.

    Accepts semicolon-separated groups, where each group is either a single
    index (single dataset) or two space-separated indices (splice two datasets).

    Example input: ``0; 1 2; 3``

    Args:
        dataset_names: List of available dataset name strings (for display only).

    Returns:
        List of group tuples, each being either ``('single', idx)`` or
        ``('splice', idx1, idx2)``.
    """
    print(f"\n{'='*60}")
    print("DATASET SELECTION AND GROUPING")
    print(f"{'='*60}")
    print("How to specify datasets:")
    print("  * Single dataset: just the index (e.g., '0')")
    print("  * Splice two datasets: two indices separated by space (e.g., '0 1')")
    print("  * Multiple groups: separate with semicolons (e.g., '0; 1 2; 3')")
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
            if len(indices) == 1:
                groups.append(("single", indices[0]))
            elif len(indices) == 2:
                groups.append(("splice", indices[0], indices[1]))
            else:
                print(f"[FAIL] Invalid group '{group_str}' - only 1 or 2 datasets per group supported")
                continue
        except ValueError:
            print(f"[FAIL] Invalid group '{group_str}' - must be integers")
            continue

    return groups


def get_atoms_per_formula_unit() -> int:
    """Prompt the user for the number of atoms per formula unit.

    Returns:
        Positive integer number of atoms per formula unit.

    Raises:
        SystemExit: If the user enters an invalid value.
    """
    print(f"\n{'='*60}")
    print("FORMULA UNIT DEFINITION")
    print(f"{'='*60}")
    print("Based on the compositions shown above, how many atoms constitute one formula unit?")
    print("(This will be used to convert total energies to energy per formula unit)")
    print("")

    try:
        atoms_per_fu = int(input("Enter number of atoms per formula unit: "))
        if atoms_per_fu <= 0:
            raise ValueError("must be positive")
        return atoms_per_fu
    except ValueError:
        sys.exit("[FAIL] Invalid input. Must be a positive integer.")


def get_dataset_labels(
    groups: list[tuple],
    dataset_names: list[str],
    raw_datasets: dict[str, tuple],
) -> dict[str, tuple]:
    """Prompt the user for dataset labels and perform any requested splicing.

    Args:
        groups: Group list from :func:`get_user_dataset_selection`.
        dataset_names: Ordered list of dataset names (by index).
        raw_datasets: Mapping from dataset name to ``(x_array, y_array)``.

    Returns:
        Dict mapping user-supplied labels to ``(x_array, y_array)`` tuples.
    """
    print(f"\n{'='*60}")
    print("DATASET LABELING AND SPLICING")
    print(f"{'='*60}")

    datasets: dict[str, tuple] = {}
    for group_num, group in enumerate(groups, 1):
        print(f"\nGroup {group_num}:")

        if group[0] == "single":
            idx = group[1]
            if 0 <= idx < len(dataset_names):
                original_name = dataset_names[idx]
                x, y = raw_datasets[original_name]

                print(f"  Dataset: {original_name}")
                print(f"  Data points: {len(x)}, c/a range: {x.min():.3f} to {x.max():.3f}")

                label = input(f"  Enter label for this dataset [{original_name}]: ").strip()
                if not label:
                    label = original_name

                datasets[label] = raw_datasets[original_name]
                print(f"  [OK] Added as: {label}")
            else:
                print(f"  [FAIL] Invalid index {idx}")

        elif group[0] == "splice":
            idx1, idx2 = group[1], group[2]
            if 0 <= idx1 < len(dataset_names) and 0 <= idx2 < len(dataset_names):
                name1, name2 = dataset_names[idx1], dataset_names[idx2]
                x1, y1 = raw_datasets[name1]
                x2, y2 = raw_datasets[name2]

                print(f"  Splicing two datasets:")
                print(f"    Dataset 1: {name1} (c/a: {x1.min():.3f}-{x1.max():.3f}, {len(x1)} points)")
                print(f"    Dataset 2: {name2} (c/a: {x2.min():.3f}-{x2.max():.3f}, {len(x2)} points)")

                default_label = f"{name1}+{name2}"
                label = input(f"  Enter label for spliced dataset [{default_label}]: ").strip()
                if not label:
                    label = default_label

                try:
                    print("  Enter c/a value where datasets should be joined:")
                    print("    (Dataset 1 will be used for c/a <= splice point)")
                    print("    (Dataset 2 will be used for c/a > splice point)")
                    splice_point = float(input("  Splice point: "))

                    spliced_data = splice_datasets(raw_datasets[name1], raw_datasets[name2], splice_point)
                    datasets[label] = spliced_data
                    print(f"  [OK] Spliced at c/a = {splice_point}, added as: {label}")
                except ValueError:
                    print("  [FAIL] Invalid splice point")
            else:
                print(f"  [FAIL] Invalid indices {idx1}, {idx2}")

    return datasets


def select_energy_reference(
    minima_info: dict[int, tuple],
) -> tuple[float, int | None]:
    """Prompt the user to select an energy reference (zero point).

    Args:
        minima_info: Mapping from integer index to ``(label, min_energy, min_ca)``
            tuples describing each dataset's global minimum.

    Returns:
        ``(reference_energy, ref_idx)`` where ``reference_energy`` is the value
        to subtract from all datasets, and ``ref_idx`` is the chosen index
        (or ``None`` if no reference was selected).
    """
    print(f"\n{'='*60}")
    print("ENERGY REFERENCE SELECTION")
    print(f"{'='*60}")
    print("You can set one of the global minima as the zero energy reference.")
    print("This will shift all datasets so that the selected minimum becomes 0 eV/f.u.")
    print("")
    print("Options:")
    print(f"  * Enter an index number [0-{len(minima_info)-1}] to set that minimum as zero")
    print("  * Press Enter to keep absolute energies (no reference)")
    print("")

    ref_choice = input("Select reference zero point: ").strip()
    reference_energy = 0.0
    ref_idx: int | None = None

    if ref_choice:
        try:
            ref_idx = int(ref_choice)
            if 0 <= ref_idx < len(minima_info):
                reference_energy = minima_info[ref_idx][1]
                ref_label = minima_info[ref_idx][0]
                print(f"[OK] Using {ref_label} minimum as zero reference")
                print(f"   (Subtracting {reference_energy:.6f} eV/f.u. from all datasets)")
            else:
                print("[FAIL] Invalid index, using absolute energies")
                ref_idx = None
        except ValueError:
            print("[FAIL] Invalid input, using absolute energies")
            ref_idx = None
    else:
        print("Using absolute energies (no reference shift)")

    return reference_energy, ref_idx
