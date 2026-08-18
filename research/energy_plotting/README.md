# energy_plotting/ — Extended Energy vs Structure Plotting

This subdirectory contains an extended energy analysis script that produces
three related plots from a single interactive session: energy vs c/a ratio,
energy vs c lattice constant, and energy vs a lattice constant.

---

## Script

### `plot_energy_vs_structure.py`

Reads VASP total-energy results from a directory tree, computes energy per
formula unit, and generates three plots:

1. **Energy vs c/a ratio** — the primary tetragonal distortion plot.
2. **Energy vs c lattice constant** — fixed-a cross-section.
3. **Energy vs a lattice constant** — fixed-c cross-section.

Each plot can have independent axis limits (prompted interactively).

---

## Prerequisites

```
pip install numpy matplotlib scipy  # scipy optional (local extrema markers)
```

Also requires the parent-directory utilities:
- `../data_processing.py`
- `../file_utils.py`

These are imported automatically via `sys.path` insertion.

---

## Expected Directory Structure

The script searches for `energies.dat` / `atom_counts.dat` pairs under a
user-specified root directory.  A typical layout:

```
calculations/
    FM/
        energies.dat        # one line per c/a value: a b c energy_eV
        atom_counts.dat     # species and atom counts
    AFM/
        energies.dat
        atom_counts.dat
    G-AFM/
        energies.dat
        atom_counts.dat
```

### energies.dat format

```
# a_Ang  b_Ang  c_Ang  total_energy_eV
3.820    3.820  3.850  -42.317
3.820    3.820  3.900  -42.331
3.820    3.820  3.950  -42.298
```

Lines beginning with `#` are ignored.

### atom_counts.dat format

```
# element  count
Cu         4
O          8
```

Lines beginning with `#` are ignored.

---

## Usage

```bash
python plot_energy_vs_structure.py --root ./calculations --atoms-per-fu 5
```

If `--root` or `--atoms-per-fu` are omitted the script prompts interactively.

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--root DIR` | (prompted) | Root directory to search for dataset pairs |
| `--atoms-per-fu N` | (prompted) | Atoms per formula unit for normalisation |

### Interactive prompts

After discovering datasets the script asks:
- Which datasets to include (all or a selection)
- Custom labels for each dataset
- y-axis limits (shared across all three plots)
- x-axis limits (separate prompt for each of the three plots)

---

## Output

Three matplotlib figure windows are displayed.  Use the matplotlib toolbar
to save them in any format (PDF, PNG, SVG, etc.).

No files are written to disk automatically.

---

## Bug fixed (vs original)

The original script used the same x-axis limits for all three plots.  The
rewritten version prompts for separate x-limits for the c/a plot, the
c-constant plot, and the a-constant plot.
