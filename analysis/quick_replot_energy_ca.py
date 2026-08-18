"""quick_replot_energy_ca.py — Fast Replot from Saved JSON Data

Replot energy vs. c/a data previously saved by energy_vs_ca.py without
re-running the interactive data-loading session.  Reads the JSON produced
by energy_vs_ca.py, optionally merges saved plot settings from a sibling
``plot_settings.json`` file, and writes a new PNG.

JSON schema (plot_data.json)
-----------------------------
::

    {
        "datasets": {
            "<label>": {"x": [float, ...], "y": [float, ...]}
        },
        "metadata": {
            "title": str,
            "xlabel": str,
            "ylabel": str,
            "x_lims": [float, float] | null,
            "y_lims": [float, float] | null
        }
    }

Usage
-----
::

    python quick_replot_energy_ca.py [data_file.json]
    python quick_replot_energy_ca.py --data plot_data.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


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


def load_settings(settings_file: Path) -> dict | None:
    """Load saved plot settings from a JSON file.

    Args:
        settings_file: Path to settings JSON (e.g. ``plot_settings.json``).

    Returns:
        Settings dict, or ``None`` if the file does not exist.
    """
    if not settings_file.exists():
        return None
    with settings_file.open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for quick_replot_energy_ca.py."""
    p = argparse.ArgumentParser(
        description="Quick replot of energy vs. c/a data from a saved JSON file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "data_file",
        nargs="?",
        type=Path,
        default=None,
        help="Path to plot_data.json (prompted if omitted).",
    )
    p.add_argument(
        "--data",
        type=Path,
        default=None,
        dest="data_file_flag",
        metavar="FILE",
        help="Alternative way to specify the data file.",
    )
    return p


def main() -> None:
    """Entry point for quick_replot_energy_ca.py."""
    args = build_parser().parse_args()

    # Resolve data file path (positional > --data > interactive)
    data_file: Path | None = args.data_file or args.data_file_flag
    if data_file is None:
        data_file = Path(input("Enter path to plot_data.json file: ").strip()).expanduser()

    try:
        datasets, metadata = load_plot_data(data_file)
        print(f"[OK] Loaded {len(datasets)} datasets from {data_file}")
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"[FAIL] {exc}")

    # Optionally apply saved settings
    settings_file = data_file.parent / "plot_settings.json"
    settings = load_settings(settings_file)

    if settings:
        print(f"[OK] Found saved settings in {settings_file}")
        use_saved = input("Use saved settings? (y/n) [y]: ").strip().lower() != "n"
    else:
        use_saved = False
        print("No saved settings found — using defaults")

    if use_saved and settings:
        title = settings.get("title", metadata.get("title", "Energy vs c/a"))
        xlabel = settings.get("xlabel", metadata.get("xlabel", "c/a ratio"))
        ylabel = settings.get("ylabel", metadata.get("ylabel", "Energy (eV/f.u.)"))
        figsize = tuple(settings.get("figsize", [8, 6]))
        grid = settings.get("grid", True)
        legend_loc = settings.get("legend_loc", "best")
        custom_styles: dict = settings.get("custom_styles", {})
        xlim = settings.get("xlim")
        ylim = settings.get("ylim")
        dpi = settings.get("dpi", 300)
    else:
        title = metadata.get("title", "Energy vs c/a")
        xlabel = metadata.get("xlabel", "c/a ratio")
        ylabel = metadata.get("ylabel", "Energy (eV/f.u.)")
        figsize = (8, 6)
        grid = True
        legend_loc = "best"
        custom_styles = {}
        xlim = metadata.get("x_lims")
        ylim = metadata.get("y_lims")
        dpi = 300

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

    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    fig.tight_layout()

    output_name = input("Output filename [quick_replot.png]: ").strip() or "quick_replot.png"
    output_path = data_file.parent / output_name
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Plot saved: {output_path}")


if __name__ == "__main__":
    main()
