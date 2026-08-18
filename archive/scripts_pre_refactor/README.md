# VASP Calculation Scripts

Scripts for running and analyzing VASP calculations on TACC Lonestar6.
All scripts live under `~/scripts/` and expect to be run from within the
relevant calculation directory unless otherwise noted.

---

## Directory Layout

```
scripts/
├── jobs/               – SLURM job generation and submission
├── magnetism/          – MAGMOM generation for coplanar orderings
├── structure/
│   ├── editor/         – POSCAR scaling, supercell creation
│   ├── elastic/        – Elastic constant calculation workflow
│   ├── phonons/        – Finite-displacement phonon workflow
│   ├── relax/          – Iterative structural relaxation
│   └── scaled/         – Lattice parameter sweeps + data parsing
└── util/               – General utilities (data parsing, timing, INCAR gen)
```

---

## Typical Workflow

```
1. crystal_system_directory_setup.sh   → create project skeleton
2. structure/relax/setup.sh            → prepare relax/ directory
3. write_jobscript.sh                  → write SLURM job, submit
   └── (repeat_relax.sh inside job)    → run VASP until converged

4a. ELASTIC PATH
    structure/elastic/setup.sh         → generate strain matrices
    structure/elastic/distribute_inputs.sh → link INCAR/KPOINTS/POTCAR
    elastic_vaspkit.sh                 → submit all strain jobs
    structure/elastic/analysis.sh      → analyze tensor with vaspkit

4b. PHONON PATH
    structure/phonons/after_relax.sh   → copy relaxed structure to phonons/
    structure/phonons/make_disp_line_arg.sh → generate displacements
    structure/phonons/fd_phonons_job.sh    → submit VASP + phonopy

4c. SCALED STRUCTURES PATH
    structure/editor/setup_varied_scale_factors.sh → generate scaled POSCARs
    structure/scaled/setup_system.sh               → build SYS/FUNC/CALC tree
    jobs/scaled_batch_basic.sh                     → chain VASP jobs
    structure/scaled/data_parser.sh                → parse results

5. util/parse_data.sh                  → general data extraction
   util/vasp_timer.sh                  → sum up CPU times
   util/collect_calcs.sh               → archive completed runs
```

---

## jobs/

### `write_jobscript.sh`
Interactive SLURM jobscript generator.

```bash
bash ~/scripts/jobs/write_jobscript.sh
```

Prompts for: calc name, nodes, cores, queue, walltime, project.
Optionally appends snippet files from `jobs/additional_functions/`.
Writes `./jobscript` in the current directory.

**Additional function snippets** (`jobs/additional_functions/`):
| File | What it adds |
|------|-------------|
| `completion_checker` | Tags job as ionic/static converged; creates `COMPLETED` |
| `converged_structural_relaxation` | Full relaxation loop with convergence check |
| `relax_until_convergence` | Relaxation loop calling setup.sh first |
| `phonons` | Single-point phonon static run |
| `phonopy` | Post-process phonopy band structure (uses conda `phonopy` env) |

---

### `write_chain_vasp_jobscript.sh`
Chain VASP runs across multiple subdirectories in one SLURM job.
Optionally carries CHGCAR/WAVECAR between steps.

```bash
# Run from within a CALC/ directory containing subdirectories with full VASP inputs
bash ~/scripts/jobs/write_chain_vasp_jobscript.sh
```

Prompts for: directory selection (indices or range), nodes/cores/queue/time,
files to copy forward (CHGCAR, WAVECAR).

---

### `scaled_batch_basic.sh`
Chain VASP across `POSCAR_scaled_*/` directories, then parse results.

```bash
bash ~/scripts/jobs/scaled_batch_basic.sh
```

---

### `elastic_vaspkit.sh`
Submit VASP for all `strain_*/` directories across all top-level directories.

```bash
# Run from the elastic/ directory
bash ~/scripts/jobs/elastic_vaspkit.sh
```

---

### `submit_multiple.sh`
Find all `jobscript` files in subdirectories and submit them all.

```bash
bash ~/scripts/jobs/submit_multiple.sh
```

Prompts for confirmation before submitting.

---

### `submit_job_loop.sh`
Submit a named jobscript in every immediate subdirectory.

```bash
bash ~/scripts/jobs/submit_job_loop.sh
# Prompts: "Name of jobscript to submit:"
```

---

## magnetism/

### `coplanar_magnetic_atoms.py`
Generate `MAGMOM` with ±M alternating every L planes, perpendicular to a
given vector. Works on any POSCAR/CONTCAR.

```bash
# Interactive
python3 ~/scripts/magnetism/coplanar_magnetic_atoms.py

# Command-line
python3 ~/scripts/magnetism/coplanar_magnetic_atoms.py \
    POSCAR [0,0,1] "Fe" 0.02 1 3.0
#   FILE   NORMAL  ATOMS  TOL  L  M
```

**Arguments:**
| Arg | Description | Default |
|-----|-------------|---------|
| POSCAR FILE | Path to POSCAR or CONTCAR | — |
| ORTHOGONAL VECTOR | Normal to planes, `[X,Y,Z]` | — |
| ATOMS | Element symbols, atom indices, or `all` | — |
| TOLERANCE | Coplanarity tolerance (Å) | `0.02` |
| LAYERS | Planes per ferromagnetic block (L) | `1` |
| MAGNITUDE | Magnetic moment magnitude (M) | `1` |

**Outputs:** `MAGMOM`, `coplanar_atoms.txt`, `run_parameters.txt`

---

### `coplanar_magnetic_ordering.py`
Same as above but accepts arbitrary P/N values instead of ±M.
Useful when the two sublattice moments differ in magnitude.

```bash
python3 ~/scripts/magnetism/coplanar_magnetic_ordering.py \
    POSCAR [0,0,1] "Fe" 0.02 1 3.0 -1.5
#   FILE   NORMAL  ATOMS TOL  L  P    N
```

---

## structure/relax/

### `setup.sh`
Copy input files into a `relax/` subdirectory.

```bash
# Run from the directory containing your input_files/ folder and relax_INCAR
bash ~/scripts/structure/relax/setup.sh input_files/
```

Requires: `input_files/POSCAR`, `input_files/POTCAR`, `input_files/KPOINTS`,
and `relax_INCAR` in the current directory.

---

### `repeat_relax.sh`
Iterative VASP relaxation loop. Runs VASP repeatedly until POSCAR ≈ CONTCAR.

```bash
# Typically called inside a SLURM job
bash ~/scripts/structure/relax/repeat_relax.sh
```

- Max 50 iterations; resumes from checkpoint if re-run.
- Logs energy and status to `relaxation.log`.
- Backs up each iteration in `relaxation_outputs/iter_N/`.

---

### `multi_stage_repeat_relax.sh`
Multi-stage relaxation with different ISIF/IBRION per stage.
Non-final stages run once; final stage repeats until converged.

```bash
bash ~/scripts/structure/relax/multi_stage_repeat_relax.sh [tolerance] ISIF1:IBRION1 ISIF2:IBRION2 ...

# Example: coarse ISIF=3 then fine ISIF=2
bash ~/scripts/structure/relax/multi_stage_repeat_relax.sh 1e-6 3:2 2:2
```

---

### `compare_poscar_contcar.sh`
Return `true`/`false` comparing POSCAR and CONTCAR numerically.

```bash
result=$(bash ~/scripts/structure/relax/compare_poscar_contcar.sh)
# Uses default tolerance 1e-8
```

---

### `compare_poscar_2_contcar.sh`
Same, but tolerance is passed as an argument.

```bash
result=$(bash ~/scripts/structure/relax/compare_poscar_2_contcar.sh 1e-6)
```

---

## structure/phonons/

### `after_relax.sh`
Set up a `phonons/` directory from a converged `relax/` directory.

```bash
# Run from the project root (parent of relax/)
bash ~/scripts/structure/phonons/after_relax.sh
```

Requires `phonons_INCAR` in the current directory and a converged `relax/`
directory. Copies CONTCAR→POSCAR, POTCAR, CHGCAR, WAVECAR.

---

### `make_disp_line_arg.sh`
Run `phonopy -d` to generate displacement POSCARs, then organize them into
numbered subdirectories with VASP input files.

```bash
# Run from inside a phonons/ directory
bash ~/scripts/structure/phonons/make_disp_line_arg.sh [--cp FILE1 FILE2 ...]

# Example: also copy CHGCAR
bash ~/scripts/structure/phonons/make_disp_line_arg.sh --cp CHGCAR
```

Default files copied to each displacement dir: `INCAR`, `KPOINTS`, `POTCAR`.

---

### `make_disp_interactive.sh`
Batch version of `make_disp_line_arg.sh` — loops over all `POSCAR*/` subdirectories.

```bash
# Run from the directory containing POSCAR*/ subdirectories
bash ~/scripts/structure/phonons/make_disp_interactive.sh
```

---

### `fd_phonons_job.sh`
Generate and submit a SLURM job that runs VASP in all displacement
subdirectories then collects force constants with `phonopy -f`.

```bash
# Run from inside the phonons/ directory
bash ~/scripts/structure/phonons/fd_phonons_job.sh [options]

# Options (all optional, with defaults shown):
#   -n, --nodes    1
#   -c, --cores    128
#   -q, --queue    normal
#   -t, --time     48:00:00
#   -a, --account  PHY24018
```

---

### `batch_fd_jobs.sh`
Run `fd_phonons_job.sh` for every `POSCAR*/` subdirectory.

```bash
bash ~/scripts/structure/phonons/batch_fd_jobs.sh
```

Prompts for SLURM resources once and applies them to all directories.

---

### `batch_disp.sh`
Loop over `POSCAR*/` directories and run `make_disp_line_arg.sh` in each.

```bash
bash ~/scripts/structure/phonons/batch_disp.sh
```

---

### `vasp_fd_batch_prep.sh`
Generate `QPOINTS` (phonon band path) in every `POSCAR*/` directory using vaspkit option 303.

```bash
bash ~/scripts/structure/phonons/vasp_fd_batch_prep.sh
```

---

### `setup_varied_phonons.sh`
Set up phonon calculations for energy minima found in `vary_inplane_lattice/`.

```bash
# Requires vary_inplane_lattice/ and phonons_base/ in the current directory
bash ~/scripts/structure/phonons/setup_varied_phonons.sh
```

---

## structure/elastic/

### `setup.sh`
Generate strain matrices using vaspkit (option 02 → 201).

```bash
# Run from the elastic/ directory (must contain POSCAR)
bash ~/scripts/structure/elastic/setup.sh
```

Requires `~/input_files/vaspkit/elastic_INPUT.in` template.

---

### `distribute_inputs.sh`
Symlink `INCAR`, `KPOINTS`, `POTCAR` into all `strain_*/` subdirectories.

```bash
bash ~/scripts/structure/elastic/distribute_inputs.sh [FILE1 FILE2 ...]
# Default: links INCAR KPOINTS POTCAR
```

---

### `analysis.sh`
Run vaspkit elastic analysis (option 02 → 201) and write `ELASTIC_INFO`.

```bash
# Run from within a completed strain calculation directory
bash ~/scripts/structure/elastic/analysis.sh
```

---

### `scaled_analysis.sh`
Run `analysis.sh` in every `POSCAR_scaled*/` subdirectory.

```bash
bash ~/scripts/structure/elastic/scaled_analysis.sh
```

---

### `collect_info.sh`
Collect all `ELASTIC_INFO` files into a single directory and extract
eigenvalue stability information.

```bash
bash ~/scripts/structure/elastic/collect_info.sh [source_dir] [target_dir]
# Defaults: source=PWD, target=elastic_results/
```

---

## structure/scaled/

### `setup_system.sh`
Build a `SYS/FUNC/CALC/POSCAR_scaled_*/` directory tree from a `POSCARs/` set.

```bash
bash ~/scripts/structure/scaled/setup_system.sh SYS CALC KPR KSCHEME FUNCTIONAL

# Example
bash ~/scripts/structure/scaled/setup_system.sh SrTiO3 scf 0.04 2 PBEsol+U
```

Selects POSCAR set interactively, generates KPOINTS and STRUCTURE_INFO
via vaspkit.

---

### `data_parser.sh`  ← **main result-collection script**
Parse energies, lattice params, band gaps, magnetization from `POSCAR_scaled_*/`.

```bash
# Interactive (asks about relax and xml)
bash ~/scripts/structure/scaled/data_parser.sh

# Non-interactive flags
bash ~/scripts/structure/scaled/data_parser.sh --relax --xml
bash ~/scripts/structure/scaled/data_parser.sh -r       # relaxation only
bash ~/scripts/structure/scaled/data_parser.sh -x       # copy xml only
```

Run from the `FUNC/CALC/` directory. Outputs written to `<FUNC>_<CALC>/`
and archived to `<FUNC>_<CALC>.tar.gz`.

| Output file | Contents |
|-------------|----------|
| `energies.dat` | dir, a, b, c (Å), E (eV) |
| `electronic_band.dat` | dir, a, b, c, gap (eV), Fermi (eV) |
| `combined_band_gaps.dat` | raw vaspkit BAND_GAP output |
| `magnetization.dat` | per-atom magnetization blocks |
| `atom_counts.dat` | species counts per directory |
| `convergence_summary.txt` | pass/fail count |

> `data_parser_yes_relax.sh` and `interactive_data_parser.sh` are wrappers
> around this script kept for backwards compatibility.

---

### `directory_restructure.sh`
Migrate old `POSCAR_scaled_*/FUNC/CALC/` layout to new `FUNC/CALC/POSCAR_scaled_*/`.

```bash
# Dry run first
DRY_RUN=1 bash ~/scripts/structure/scaled/directory_restructure.sh

# Live run
bash ~/scripts/structure/scaled/directory_restructure.sh
```

---

## structure/editor/

### `poscar_scaler.py` / `scaling_poscar.py`
Scale POSCAR lattice vectors — single file or batch sweep.

```bash
# Interactive
python3 ~/scripts/structure/editor/poscar_scaler.py

# Single scale (uniform)
python3 ~/scripts/structure/editor/poscar_scaler.py POSCAR single 1.02

# Single scale (anisotropic)
python3 ~/scripts/structure/editor/poscar_scaler.py POSCAR single 1.02 1.0 0.98

# Sweep (generates all combinations)
python3 ~/scripts/structure/editor/poscar_scaler.py POSCAR multiple \
    0.95 0.95 0.95  1.05 1.05 1.05  0.01 0.01 0.01
#   xmin ymin zmin  xmax ymax zmax   incx incy incz
```

---

### `setup_varied_scale_factors.sh`
Generate a `scale_X/POSCAR_z_Z/` directory tree with scaled POSCARs and KPOINTS.

```bash
# Interactive
bash ~/scripts/structure/editor/setup_varied_scale_factors.sh

# Command-line (xy coupled, z swept)
bash ~/scripts/structure/editor/setup_varied_scale_factors.sh -xy 0.95:1.05:0.01 -z 0.95:1.05:0.01
```

Coupling options: `-x`, `-y`, `-z`, `-xy`, `-xz`, `-yz`, `-xyz`.

---

### `change_scaling_factors.py`
Replace the POSCAR scale-factor line (line 2) with three values.

```bash
python3 ~/scripts/structure/editor/change_scaling_factors.py X Y Z
# Modifies POSCAR in-place
```

---

### `loop_scale_factor_changer.sh`
Apply `change_scaling_factors.py` to every `POSCAR_scaled*/` subdirectory.

```bash
bash ~/scripts/structure/editor/loop_scale_factor_changer.sh X Y Z
```

---

### `ca_ratio_volume_constant.py`
Scale c/a ratio while keeping unit cell volume constant.

```bash
python3 ~/scripts/structure/editor/ca_ratio_volume_constant.py POSCAR ratios.txt
# ratios.txt: one c/a ratio per line
```

---

### `volume.py`
Print unit cell volume of a POSCAR.

```bash
python3 ~/scripts/structure/editor/volume.py POSCAR
```

---

### `check_scaling.py`
Validate that `POSCAR_scaled_*` files have the correct lattice lengths
relative to the reference `POSCAR`.

```bash
# Run from the directory containing POSCAR and POSCAR_scaled_* files
python3 ~/scripts/structure/editor/check_scaling.py
```

---

### `super_cell_maker.sh`
Generate phonopy supercells for all `POSCAR_*/` subdirectories, inject
MAGMOM if present, and replace POSCAR with SPOSCAR.

```bash
# Run from the directory containing POSCAR_*/ subdirectories
bash ~/scripts/structure/editor/super_cell_maker.sh
# Prompts: supercell dimensions X Y Z
```

Requires `../INCARs/base_INCAR` (one level up from current directory).

---

### `loop_over_inplane_lattice_constants.sh`
Loop over a user-selected directory and apply scale factor changes.

```bash
bash ~/scripts/structure/editor/loop_over_inplane_lattice_constants.sh
```

---

## util/

### `parse_data.sh`
General VASP result parser — searches for OUTCARs up to 2 levels deep.

```bash
bash ~/scripts/util/parse_data.sh [options]
#   -r, --relax   ionic convergence check + use CONTCAR
#   -x, --xml     copy vasprun.xml
```

Outputs: `energies.dat`, `magnetization.dat`, `atom_counts.dat`,
`convergence_summary.txt` in `<FUNC>_<CALC>/`.

---

### `generate_INCAR.sh`
Interactive INCAR generator from a block-structured template.

```bash
bash ~/scripts/util/generate_INCAR.sh
```

Reads `~/scripts/util/templates/INCAR.template`, lists available blocks,
prompts for values, writes `INCAR`.

---

### `vasp_timer.sh`
Sum elapsed times from all `*/OUTCAR` files in the current directory.

```bash
bash ~/scripts/util/vasp_timer.sh
# Writes vasp_timing_summary.txt
```

---

### `collect_calcs.sh`
Copy completed calculation directories (those with timing in OUTCAR)
to a new directory while stripping large files.

```bash
bash ~/scripts/util/collect_calcs.sh <dirname>
# Copies all dirs named <dirname> that have a complete OUTCAR
```

---

### `distribute_inputs.sh`
Interactively copy selected files from the current directory into all
subdirectories matching a pattern.

```bash
bash ~/scripts/util/distribute_inputs.sh
# Prompts: pattern, files to copy
```

---

### `delete_WAVECAR.sh`
Find and delete all WAVECAR files (with size report and confirmation).

```bash
bash ~/scripts/util/delete_WAVECAR.sh
```

---

### `crystal_system_directory_setup.sh`
Create a project directory skeleton with `electrons/`, `elastic/`,
`phonons/`, `relax/` subdirectories.

```bash
bash ~/scripts/util/crystal_system_directory_setup.sh SYSTEM PSEUDO KPR KSCHEME DIRNAME

# Example
bash ~/scripts/util/crystal_system_directory_setup.sh SrTiO3 PBE 0.04 2 STO_study
```

Requires `~/POSCARs/SYSTEM` to exist.

---

### `energy_minima.py`
Find local energy minima from `energies.dat` files.

```bash
python3 ~/scripts/util/energy_minima.py 'path/to/dirs/POSCAR_z_*'
# Prints directory names of local minima to stdout
```

---

### `parse_poscar.py`
Print lattice vector lengths (A B C in Å) from a POSCAR file.

```bash
python3 ~/scripts/util/parse_poscar.py POSCAR
# Output: A_length B_length C_length
```

---

### `util/batch_calcs/bench_INCAR.sh`
Create subdirectories to test a range of values for one INCAR parameter.

```bash
# Run from a directory with POSCAR, POTCAR, INCAR, KPOINTS
bash ~/scripts/util/benchmarks/bench_INCAR.sh
# Prompts: parameter name (e.g. ENCUT), values (e.g. 400:600:50)
```

---

### `util/batch_calcs/basic_loop_cmd.sh`
Template: loop over all subdirectories and run a command.
Edit the marked section inside the script to add your commands.

---

### `util/batch_calcs/follow_up_calc.sh` / `follow_up_calculations.sh`
Set up a follow-up calculation from an existing set of POSCAR_* directories,
optionally varying INCAR parameters.

```bash
bash ~/scripts/util/batch_calcs/follow_up_calculations.sh
```

---

## Common SLURM Defaults

| Parameter | Default |
|-----------|---------|
| Account | `PHY24018` |
| Queue | `normal` |
| Nodes | `1` |
| Cores | `128` |
| Walltime | `48:00:00` |
| VASP | `vasp/6.3.0` |
| MPI | `intel/19.1.1 impi/19.0.9` |

These defaults appear in all job-generating scripts and can be overridden
via prompts or command-line flags.

---

## Tips

- **Checkpoint/resume:** `repeat_relax.sh` and the chain job scripts both
  use `COMPLETED` sentinel files. Delete a `COMPLETED` file to force a
  directory to re-run.
- **Disk cleanup:** Run `delete_WAVECAR.sh` after jobs finish if you don't
  need wavefunctions for restart.
- **Data safety:** Run `collect_calcs.sh` to archive results before
  anything gets purged from scratch.
- **Path convention:** All scripts use `$HOME/scripts/` as the base.
  If you move the scripts directory, update `$HOME/scripts` references or
  add `~/scripts` to `$PATH`.
