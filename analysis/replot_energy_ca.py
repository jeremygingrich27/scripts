"""replot_energy_ca.py — Interactive Replot from Saved JSON Data

Loads energy vs. c/a data previously saved by energy_vs_ca.py, provides
interactive options to customise colours/markers/labels, and saves the
result to a new PNG file.  Plot settings can optionally be saved to
``plot_settings.json`` for use with quick_replot_energy_ca.py.

JSON schema (plot_data.json)
-----------------------------
Same schema as produced by energy_vs_ca.py — see quick_replot_energy_ca.py
or energy_vs_ca.py for the full specification.

Usage
-----
::

    python replot_energy_ca.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_plot_data(
    data_file: Path,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], dict]:
    """Load datasets and metadata from a plot_data.json file.

    Args:
        data_file: Path to the JSON file produced by energy_vs_ca.py.

    Returns:
        ``(datasets, metadata)`` where ``datasets`` maps labels to
        ``(x_array, y_array)`` and ``metadata`` is the raw metadata dict.

    Raises:
        FileNotFoundError: If *data_file* does not exist.
        ValueError: If the JSON structure is invalid.
    """
    if not data_file.exists():
        raise FileNotFoundError(f"Data file not found: {data_file}")

    with data_file.open() as f:
        data = json.load(f)

    if "datasets" not in data:
        raise ValueError("JSON missing 'datasets' key.")

    datasets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for label, values in data["datasets"].items():
        datasets[label] = (np.array(values["x"]), np.array(values["y"]))

    return datasets, data.get("metadata", {})


def ask_limits(
    name: str,
    current_limits: tuple[float, float] | None = None,
) -> list[float] | None:
    """Prompt the user for axis limits, optionally showing current values.

    Args:
        name: Axis identifier, e.g. ``'x'`` or ``'y'``.
        current_limits: Current (min, max) tuple for display, or ``None``.

    Returns:
        ``[min, max]`` on success, ``None`` if blank or unparseable.
    """
    if current_limits:
        prompt = (
            f"Enter {name}-axis limits "
            f"(current: {current_limits[0]:.3f} to {current_limits[1]:.3f}) "
            "or leave blank: "
        )
    else:
        prompt = f"Enter {name}-axis limits (min max) or leave blank: "

    raw = input(prompt)
    try:
        parts = raw.split()
        if len(parts) == 2:
            return [float(parts[0]), float(parts[1])]
    except ValueError:
        pass
    if raw.strip():
        print(f"Invalid {name}-axis limits. Using auto-scaling.")
    return None


# ---------------------------------------------------------------------------
# Appearance customisation
# ---------------------------------------------------------------------------

def get_available_markers() -> list[str]:
    """Return a list of common matplotlib marker codes."""
    return ["o", "s", "^", "v", "<", ">", "D", "p", "h", "*", "+", "x"]


def get_available_linestyles() -> list[str]:
    """Return a list of matplotlib linestyle strings."""
    return ["-", "--", "-.", ":", "None"]


def customize_styles(
    datasets: dict,
) -> tuple[dict, dict]:
    """Interactively customise colours, markers, and line styles per dataset.

    Args:
        datasets: Current datasets dict (keys only used for display).

    Returns:
        ``(datasets, custom_styles)`` where ``custom_styles`` maps dataset
        labels to matplotlib plot-kwargs dicts.
    """
    print("\nAvailable markers:", get_available_markers())
    print("Available line styles:", get_available_linestyles())

    custom_styles: dict[str, dict] = {}
    for label in datasets:
        print(f"\nCustomising {label}:")
        color = input("  Color [default]: ").strip()
        marker = input("  Marker [o]: ").strip() or "o"
        linestyle = input("  Line style [-]: ").strip() or "-"
        linewidth_str = input("  Line width [1.0]: ").strip()

        style: dict = {"marker": marker, "linestyle": linestyle}
        if color:
            style["color"] = color
        if linewidth_str:
            try:
                style["linewidth"] = float(linewidth_str)
            except ValueError:
                pass

        custom_styles[label] = style

    return datasets, custom_styles


def customize_labels(datasets: dict) -> tuple[dict, dict]:
    """Interactively rename dataset labels.

    Args:
        datasets: Mapping from current label to ``(x, y)`` data.

    Returns:
        ``(new_datasets, {})`` with renamed keys.
    """
    new_datasets: dict = {}
    for label, data in datasets.items():
        new_label = input(f"New label for '{label}' [keep current]: ").strip()
        new_datasets[new_label if new_label else label] = data
    return new_datasets, {}


def customize_plot_appearance(
    datasets: dict,
) -> tuple[dict, dict]:
    """Top-level appearance customisation menu.

    Args:
        datasets: Current datasets dict.

    Returns:
        ``(datasets, custom_styles)`` tuple after user customisation.
    """
    print("\nCustomise plot appearance:")
    print("  1. Change colours, markers, and line styles")
    print("  2. Modify labels")
    print("  3. Skip customisation")

    choice = input("Enter choice (1-3): ").strip()
    if choice == "1":
        return customize_styles(datasets)
    elif choice == "2":
        return customize_labels(datasets)
    return datasets, {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for replot_energy_ca.py."""
    data_file = Path(input("Enter path to plot_data.json file: ").strip()).expanduser()

    try:
        datasets, metadata = load_plot_data(data_file)
        print(f"\n[OK] Loaded {len(datasets)} datasets:")
        for label, (x, y) in datasets.items():
            print(f"  {label}: {len(x)} points, c/a {x.min():.3f}-{x.max():.3f}")
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"[FAIL] {exc}")

    # Compute data ranges for displaying as hints to the user
    all_x = np.concatenate([x for x, _ in datasets.values()])
    all_y = np.concatenate([y for _, y in datasets.values()])
    x_range: tuple[float, float] = (float(all_x.min()), float(all_x.max()))
    y_range: tuple[float, float] = (float(all_y.min()), float(all_y.max()))

    datasets, custom_styles = customize_plot_appearance(datasets)

    # Plot settings
    print("\nPlot settings:")
    title = input(f"Title [{metadata.get('title', '')}]: ").strip() or metadata.get("title", "")
    xlabel = input(f"X-axis label [{metadata.get('xlabel', '')}]: ").strip() or metadata.get("xlabel", "c/a ratio")
    ylabel = input(f"Y-axis label [{metadata.get('ylabel', '')}]: ").strip() or metadata.get("ylabel", "Energy (eV/f.u.)")

    figsize_input = input("Figure size (width height) [8 6]: ").strip()
    try:
        figsize = tuple(map(float, figsize_input.split())) if figsize_input else (8, 6)
    except ValueError:
        figsize = (8, 6)

    grid = input("Show grid? (y/n) [y]: ").strip().lower() != "n"

    print("\nLegend options: 1=best  2=upper right  3=lower right  "
          "4=upper left  5=lower left  6=below  7=none")
    legend_choice = input("Legend location [1]: ").strip() or "1"
    legend_locations = {
        "1": "best", "2": "upper right", "3": "lower right",
        "4": "upper left", "5": "lower left", "6": "below", "7": "none",
    }
    legend_loc = legend_locations.get(legend_choice, "best")

    # Build plot
    fig, ax = plt.subplots(figsize=figsize)

    for label, (x, y) in datasets.items():
        kwargs: dict = {"label": label}
        if label in custom_styles:
            kwargs.update(custom_styles[label])
        else:
            kwargs.update({"marker": "o", "linestyle": "-"})
        ax.plot(x, y, **kwargs)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    if grid:
        ax.grid(True, alpha=0.3)

    if legend_loc == "below":
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(datasets), 3))
        fig.subplots_adjust(bottom=0.15)
    elif legend_loc != "none":
        ax.legend(loc=legend_loc)

    xlim = ask_limits("x", x_range)
    ylim = ask_limits("y", y_range)
    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    fig.tight_layout()

    output_name = input("Output filename [replotted_energies.png]: ").strip() or "replotted_energies.png"
    output_path = data_file.parent / output_name

    dpi_str = input("DPI [300]: ").strip()
    try:
        dpi = int(dpi_str) if dpi_str else 300
    except ValueError:
        dpi = 300

    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"\n[OK] Plot saved: {output_path}")

    # Optionally persist settings
    if input("Save current settings for future use? (y/n) [n]: ").strip().lower() == "y":
        settings = {
            "title": title,
            "xlabel": xlabel,
            "ylabel": ylabel,
            "figsize": list(figsize),
            "grid": grid,
            "legend_loc": legend_loc,
            "custom_styles": custom_styles,
            "xlim": xlim,
            "ylim": ylim,
            "dpi": dpi,
        }
        settings_file = data_file.parent / "plot_settings.json"
        with settings_file.open("w") as f:
            json.dump(settings, f, indent=2)
        print(f"[OK] Settings saved: {settings_file}")


if __name__ == "__main__":
    main()
