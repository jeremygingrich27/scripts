# research/ — Computational Materials Science Scripts

A collection of Python and shell scripts for VASP-based computational
materials science workflows: energy analysis, phonon calculation,
symmetry-mode analysis, magnetic structure assignment, and crystal
structure manipulation.

---

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| numpy | Numerical arrays | `pip install numpy` |
| matplotlib | Plotting | `pip install matplotlib` |
| scipy | Optional: local extrema in energy plots | `pip install scipy` |
| phonopy | Phonon calculations (`phonopy-load`) | `pip install phonopy` |
| sumo | DOS/band plotting (`sumo-dosplot`) | `pip install sumo` |
| v_sim | Crystal structure visualiser (animations) | distro package or source |

---

## Data File Formats

### energies.dat
Produced by VASP total-energy runs; one line per structure:

```
a_Ang  b_Ang  c_Ang  energy_eV
3.82   3.82   3.91   -42.317
```

### atom_counts.dat
Maps VASP POSCAR species to atom counts, used by `file_utils.py`:

```
# element  count
Cu         4
O          8
```

### plot_data.json
Produced by `energy_vs_ca.py`; consumed by `quick_replot_energy_ca.py`
and `replot_energy_ca.py`:

```json
{
  "datasets": [
    {
      "label": "FM",
      "x": [0.95, 1.00, 1.05],
      "y": [-1.23, -1.30, -1.25],
      "x_min": 1.00,
      "y_min": -1.30
    }
  ],
  "atoms_per_fu": 5
}
```

---

## Scripts

### Shared Utilities

| File | Purpose |
|------|---------|
| `data_processing.py` | Parse `energies.dat`, compute energies per formula unit, sort by c/a. |
| `file_utils.py` | Discover paired `(energies.dat, atom_counts.dat)` file sets. |
| `user_interface.py` | Shared interactive prompts (root directory, axis limits, dataset selection). |

**`data_processing.py`** key function:

```python
parse_energy_data(fpath, atoms_per_fu, total_atoms)
# Returns: (c_over_a, energy_per_fu, a_arr, b_arr, c_arr)  — all sorted by c/a
```

---

### Energy Analysis

| File | Purpose |
|------|---------|
| `energy_vs_ca.py` | Plot energy per formula unit vs c/a ratio; saves `plot_data.json`. |
| `energy_vs_structure.py` | Plot energy vs c/a, c-constant, and a-constant in three panels. |
| `quick_replot_energy_ca.py` | Fast replot from an existing `plot_data.json` without re-parsing. |
| `replot_energy_ca.py` | Replot with interactive axis/style customisation. |
| `magnetization_vs_ca.py` | Plot per-atom magnetization vs c/a ratio from OUTCAR data. |
| `dyn_matrix.py` | Convert `.npy` dynamical matrix files to plain text. |

**Usage:**

```bash
python energy_vs_ca.py --root ./calculations --atoms-per-fu 5
python energy_vs_structure.py --root ./calculations --atoms-per-fu 5
python quick_replot_energy_ca.py plot_data.json
python replot_energy_ca.py plot_data.json
python dyn_matrix.py ./npy_directory
```

The `energy_plotting/` subdirectory contains an extended version:
see `energy_plotting/README.md`.

---

### Magnetic Structure Scripts

| File | Purpose |
|------|---------|
| `antiferromagnetic_planes.py` | Assign alternating +/- MAGMOM values to atomic planes; writes INCAR block. |
| `coplanar_magnetic_atoms.py` | Identify coplanar atoms and assign in-plane ferromagnetic / inter-plane antiferromagnetic moments. |

**Usage:**

```bash
python antiferromagnetic_planes.py [POSCAR] [nx ny nz] --atoms Cu --layers 2 --magnitude 1.0
python coplanar_magnetic_atoms.py
```

---

### Crystal Structure Manipulation

| File | Purpose |
|------|---------|
| `octahedral_tilt.py` | Apply Glazer octahedral tilt distortions to a POSCAR; supports all 15 tilt types. |

**Glazer tilt types supported:**

```
a+a+a+  a+a+a-  a+a-a+  a-a-a-
a0a0a+  a0a0a-  a0b+b+  a0b+b-  a0b-b-
a0a0b+  a0a0b-  a+a0c+  a-a0c-
a+b+c+  a-b-c-
```

Notation: `+` = in-phase tilt, `-` = out-of-phase, `0` = no tilt.

**Usage:**

```bash
python octahedral_tilt.py --poscar POSCAR --tilt a-a-a- --magnitude 0.02 --output POSCAR_tilted
```

---

### Phonon / Matrix Scripts

| File | Purpose |
|------|---------|
| `plot_phonon.py` | Plot phonon band structure from a `PHONON_BAND.dat` file. |
| `normalize_matrix.py` | Column-normalize a CSV displacement matrix; checks orthogonality. |
| `load_npy_files.py` | Load `.npy` arrays and print/save them as plain text. |

See `phonons/README.md` for the full phonon analysis pipeline.

---

### Shell Scripts

| File | Purpose |
|------|---------|
| `animate_phonons.sh` | Generate phonon animation `.ascii` files from high-symmetry points and open with V_Sim. |
| `batch_sumo_dosplot.sh` | Interactively build and batch-run `sumo-dosplot` across multiple directories. |
| `loop_extract_files.sh` | Extract all `.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tgz` archives in the current directory. |
| `run_vsim.sh` | Select and open a `.ascii` phonon animation file with V_Sim. |

**Usage:**

```bash
# In a phonopy working directory with HIGH_SYMMETRY_POINTS:
bash animate_phonons.sh

# In a parent directory with vasprun.xml subdirectories:
bash batch_sumo_dosplot.sh

# In a directory with archive files to unpack:
bash loop_extract_files.sh

# In a directory with .ascii animation files:
bash run_vsim.sh
```

---

## Typical Workflow

```
VASP calculation
      |
      v
energies.dat + atom_counts.dat
      |
      +---> energy_vs_ca.py ---------> plot_data.json --> replot_energy_ca.py
      |
      +---> energy_vs_structure.py --> three-panel plot
      |
OUTCAR
      |
      +---> phonons/phonon_extractor.py --> phonon_frequencies.csv
      |                                     phonon_displacements.csv
      |
      +---> phonons/smodes_extractor.py --> <stem>_matrix.csv (symmetry modes)
      |
      +---> phonons/normalize_matrix.py --> <stem>_normed.csv
      |
      +---> phonons/smodes_projected_onto_phmodes.py --> projection.csv
      |
      +---> phonons/process_phonon_frequency_smode_projection.py --> analysis.txt
```
