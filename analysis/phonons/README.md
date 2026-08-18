# phonons/ — Phonon Mode Analysis Pipeline

Four scripts that form a pipeline for correlating VASP phonon modes with
symmetry modes (irreducible representations) from SMODES.

---

## Pipeline Overview

```
VASP OUTCAR
     |
     v
phonon_extractor.py
     |
     +---> phonon_frequencies.csv   (mode index + raw frequency line)
     +---> phonon_displacements.csv (components x modes displacement matrix)
     |
     v                                SMODES displacement file
normalize_matrix.py                         |
     |                                      v
     +---> <stem>_normed.csv        smodes_extractor.py
                |                          |
                |                          +---> <stem>_matrix.csv
                |                          +---> <stem>_normfactors.txt
                v                          |
     smodes_projected_onto_phmodes.py <----+
                |
                +---> <stem>_projection.csv   (sym_modes x ph_modes)
                |
                v
     process_phonon_frequency_smode_projection.py
                |
                +---> <stem>_analysis.txt   (per-mode irrep assignments)
```

---

## Scripts

### 1. `phonon_extractor.py`

Reads a VASP OUTCAR and extracts all phonon mode frequencies and
displacement eigenvectors.

**Usage:**

```bash
python phonon_extractor.py [--outcar OUTCAR] \
    [--freq-output phonon_frequencies.csv] \
    [--disp-output phonon_displacements.csv]
```

**Output files:**

`phonon_frequencies.csv` — one row per mode:

```
ModeIndex,FrequencyLine
1,"  1 f  =  12.345 THz   77.573 2PiTHz  411.5 cm-1  ..."
2,"  2 f/i=   0.123 THz   ..."   <- imaginary frequency (flagged)
```

`phonon_displacements.csv` — transposed displacement matrix:

```
Atom_Displacement,Mode1,Mode2,...
atom1_dx,0.001,-0.002,...
atom1_dy,...
atom1_dz,...
atom2_dx,...
```

Rows are displacement components (3 per atom); columns are modes.
Imaginary modes (lines containing `f/i`) are flagged in the console output.

---

### 2. `smodes_extractor.py`

Parses an SMODES displacement file, reorders atoms by element and number
within each mode block, and writes a displacement matrix CSV.

**Usage:**

```bash
python smodes_extractor.py <smodes_displacement_file>
```

**Expected input format:**

```
Displacive mode definitions
atom    x        y        z        dx      dy      dz
Cu1 normfactor 0.12345 ...
Cu1   0.0  0.5  0.0   0.01   0.00   0.00
Cu2   0.5  0.0  0.0   0.00   0.01   0.00
...
```

Each mode block begins with a `normfactor` header line.  Lines with fewer
than 7 columns are skipped.

**Output files:**

- `<stem>_matrix.csv` — displacement matrix (components x modes)
- `<stem>_normfactors.txt` — all normfactor header lines
- `<stem>.bak` — backup of the original file before atom reordering

**Note:** the original file is overwritten with atoms reordered by element
name then trailing index (e.g. Ca1, Ca2, ..., Cu1, Cu2, ...).  A `.bak`
backup is always created first.

---

### 3. `normalize_matrix.py`  *(in parent directory)*

Column-normalises a CSV displacement matrix so each column has unit norm,
then checks pairwise orthogonality.

```bash
python ../normalize_matrix.py --input <stem>_matrix.csv \
    --output <stem>_normed.csv [--tolerance 1e-10]
```

---

### 4. `smodes_projected_onto_phmodes.py`

Computes the projection of symmetry modes onto phonon modes:

```
P = S^T @ Ph
```

where S is the symmetry-mode matrix (components x sym_modes) and Ph is the
phonon displacement matrix (components x ph_modes).  Element P[i,j] is the
dot product of symmetry mode i with phonon mode j.

**Usage:**

```bash
python smodes_projected_onto_phmodes.py \
    SMODE_CSV PHMODE_CSV \
    [--threshold 0.1] [--top 10] [--output projection.csv]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `SMODE_CSV` | (required) | Normalised symmetry-mode matrix CSV |
| `PHMODE_CSV` | (required) | Phonon displacement matrix CSV |
| `--threshold T` | 0.1 | Minimum \|projection\| to report |
| `--top N` | 10 | Number of strongest projections to display |
| `--output FILE` | `<smode_stem>_projection.csv` | Output CSV filename |

**Output:** `<stem>_projection.csv` — rows are symmetry modes, columns are
phonon modes.

---

### 5. `process_phonon_frequency_smode_projection.py`

Correlates phonon frequencies with symmetry-mode (irrep) projections.
For each phonon mode, lists all irreducible representations whose projection
value exceeds a configurable threshold, sorted by descending absolute value.

**Usage:**

```bash
python process_phonon_frequency_smode_projection.py \
    FREQ_CSV IRREP_CSV \
    [--threshold T] [--header TEXT] [--output FILE] [--decimals N]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `FREQ_CSV` | (required) | `phonon_frequencies.csv` from `phonon_extractor.py` |
| `IRREP_CSV` | (required) | Projection CSV from `smodes_projected_onto_phmodes.py` |
| `--threshold T` | (prompted) | Minimum \|projection\| to include in output |
| `--header TEXT` | (prompted) | Title line for the output report |
| `--output FILE` | `<freq>_<irrep>_analysis.txt` | Output filename |
| `--decimals N` | 6 | Decimal places for projection values |

**Output:** plain-text report, one block per phonon mode:

```
Mode 42:
  42 f  =  14.231 THz   89.453 2PiTHz  474.7 cm-1  ...
------------------------------------------------------------
Irrep_A2u                                            0.987654
Irrep_Eu                                             0.123456
```

---

## Complete Example

```bash
# 1. Extract phonon data from VASP
python phonon_extractor.py --outcar OUTCAR

# 2. Extract symmetry modes from SMODES output
python smodes_extractor.py smodes_displacements.txt

# 3. Normalise the symmetry-mode matrix
python ../normalize_matrix.py \
    --input smodes_displacements_matrix.csv \
    --output smodes_normed.csv

# 4. Compute projections
python smodes_projected_onto_phmodes.py \
    smodes_normed.csv phonon_displacements.csv \
    --threshold 0.05 --top 20 \
    --output smodes_projection.csv

# 5. Correlate with frequencies
python process_phonon_frequency_smode_projection.py \
    phonon_frequencies.csv smodes_projection.csv \
    --threshold 0.05 --header "BaTiO3 Gamma-point analysis" \
    --output batio3_analysis.txt
```
