# VASP Calculation Scripts

Scripts for running and analyzing VASP calculations on TACC Lonestar6.
All scripts live under `~/scripts/` and expect to be run from within the
relevant calculation directory unless otherwise noted.

---

## Directory Layout

```
scripts/
├── lib/                – shared SLURM defaults + helpers (sourced by job scripts)
├── jobs/               – SLURM job generation and submission
├── magnetism/          – MAGMOM generation for coplanar orderings
├── structure/
│   ├── editor/         – POSCAR scaling, supercell creation
│   ├── elastic/        – Elastic constant calculation workflow
│   ├── phonons/        – Finite-displacement phonon workflow
│   ├── relax/          – Iterative structural relaxation
│   └── scaled/         – Lattice parameter sweeps + data parsing
│       └── vary_inplane/ – AFII in-plane×c seeded-CHGCAR branch decks
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

> All job-generating scripts source `lib/slurm_defaults.sh` for their cluster
> defaults (account, queue, nodes, cores, walltime, modules). Change a default
> there once and it applies everywhere; override per-run with a flag or by
> exporting the matching `VASP_*` variable. Every script supports `-h/--help`.

### `write_jobscript.sh`
SLURM jobscript generator — interactive, or fully flag-driven.

```bash
bash ~/scripts/jobs/write_jobscript.sh                       # interactive
bash ~/scripts/jobs/write_jobscript.sh -j relax -t 24:00:00  # override values
bash ~/scripts/jobs/write_jobscript.sh -y -j scf --add relax_until_convergence
```

Flags: `-j/--name`, `-N/--nodes`, `-n/--cores`, `-q/--queue`, `-t/--time`,
`-A/--account`, `-d/--dir`, `--add "1 3"` (snippet by number *or* name),
`-y/--yes` (non-interactive). Writes `./jobscript`. Snippets come from
`jobs/additional_functions/`.

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
# Run from a CALC/ directory whose subdirectories hold full VASP inputs
bash ~/scripts/jobs/write_chain_vasp_jobscript.sh                       # interactive
bash ~/scripts/jobs/write_chain_vasp_jobscript.sh -y \
    --dirs "step1 step2 step3" --copy "CHGCAR WAVECAR" -t 24:00:00 --submit
# distinct filename + queue name (e.g. two chains in one dir):
bash ~/scripts/jobs/write_chain_vasp_jobscript.sh -y --dirs "a b c" --copy CHGCAR \
    --out jobscript_compressed --name mysys_comp
```

Flags: `--dirs "A B C"` (order to chain), `--copy "F1 F2"` (files forward),
`--out FILE` (jobscript filename, default `chain_vasp_jobscript.sh`),
`--name NAME` (SLURM `-J`, default `chain_vasp`), the SLURM flags
(`-N -n -q -t -A`), `--submit` (sbatch after writing, asks to confirm),
`-y/--yes`. Skips directories that already contain a `COMPLETED` file. Use
`--out`/`--name` to write more than one chain into the same directory without
clobbering (e.g. the `vary_inplane` compressed + elongated branches).

---

### `scaled_batch_basic.sh`
Chain VASP across `POSCAR_scaled_*/` directories, then parse results.

```bash
bash ~/scripts/jobs/scaled_batch_basic.sh                 # interactive
bash ~/scripts/jobs/scaled_batch_basic.sh -y --submit     # all dirs, submit
```

Same flags as `write_chain_vasp_jobscript.sh`. No longer auto-submits — use
`--submit` (which confirms first unless `-y`).

---

### `elastic_vaspkit.sh`
Build (and optionally submit) a job running VASP in all `strain_*/` directories
across all top-level directories.

```bash
# Run from the directory holding the strain groups (C11_C12_I/, C44/, ...)
bash ~/scripts/jobs/elastic_vaspkit.sh                    # write only
bash ~/scripts/jobs/elastic_vaspkit.sh -y --submit -t 24:00:00
```

Flags: SLURM flags (`-N -n -q -t -A`), `--submit`, `-y/--yes`.

---

### `submit_jobs.sh`
Submit a jobscript in each matching subdirectory (merges the old
`submit_multiple.sh` + `submit_job_loop.sh`).

```bash
bash ~/scripts/jobs/submit_jobs.sh                 # submit ./*/jobscript, after confirming
bash ~/scripts/jobs/submit_jobs.sh --name relax.slurm   # a differently named file
bash ~/scripts/jobs/submit_jobs.sh -r -y           # recursive, no confirmation
```

Flags: `--name NAME` (default `jobscript`), `-r/--recursive` (any depth vs.
immediate subdirs), `-y/--yes`. Prints a found/submitted/failed summary.

---

## magnetism/

### `coplanar_magmom.py`
Group selected atoms into planes perpendicular to a vector and assign
alternating `MAGMOM` values in blocks of L planes. Merges the old
`coplanar_magnetic_atoms.py` (±M) and `coplanar_magnetic_ordering.py` (P/N)
into one tool with two modes. Has `-h`; positional args are optional and
prompted for when omitted in a terminal.

```bash
python3 ~/scripts/magnetism/coplanar_magmom.py                       # interactive
python3 ~/scripts/magnetism/coplanar_magmom.py POSCAR "[0,0,1]" Fe -M 3.0
python3 ~/scripts/magnetism/coplanar_magmom.py POSCAR "[0,0,1]" "Fe Ni" -L 2 --pn 2.5 -1.5
```

| Arg / flag | Description | Default |
|-----|-------------|---------|
| `poscar` | Path to POSCAR or CONTCAR | — (prompt) |
| `vector` | Plane normal `[X,Y,Z]` | `[0,0,1]` |
| `atoms` | Element symbols, 1-based indices, or `all` | `all` |
| `-t, --tol` | Coplanarity tolerance (Å) | `0.02` |
| `-L, --layers` | Planes per ferromagnetic block | `1` |
| `-M, --moment` | Moment magnitude → blocks `+M / -M` | (this mode default; M=`1`) |
| `--pn P N` | Explicit positive/negative block values (numbers or placeholders) | — |

`-M` and `--pn` are mutually exclusive. **Outputs:** `MAGMOM`,
`coplanar_atoms.txt`, `run_parameters.txt`.

---

## structure/relax/

### `setup.sh`
Copy a folder of VASP inputs into a `relax/` directory and install a relaxation INCAR.

```bash
# Run from the directory containing your input folder and the relax INCAR
bash ~/scripts/structure/relax/setup.sh input_files/
bash ~/scripts/structure/relax/setup.sh --incar scf_INCAR --name relax2 -f input_files/
```

Flags: `--incar FILE` (default `relax_INCAR`), `--name DIR` (default `relax`),
`-f/--force` (overwrite). Requires `POSCAR/POTCAR/KPOINTS` in the input folder.

---

### `repeat_relax.sh`
Iterative VASP relaxation loop. Runs VASP repeatedly until POSCAR ≈ CONTCAR.

```bash
# Typically called inside a SLURM job
bash ~/scripts/structure/relax/repeat_relax.sh
bash ~/scripts/structure/relax/repeat_relax.sh --max-iter 30 --tol 1e-6 --no-kpoints
```

Flags: `--max-iter N` (default 50), `--tol VALUE` (default 1e-8), `--no-kpoints`
(skip the per-iteration vaspkit KPOINTS regeneration). Resumes from checkpoint
if re-run; logs to `relaxation.log`; backs up each iteration in
`relaxation_outputs/iter_N/`.

---

### `multi_stage_repeat_relax.sh`
Multi-stage relaxation with different ISIF/IBRION per stage.
Non-final stages run once; final stage repeats until converged.

```bash
bash ~/scripts/structure/relax/multi_stage_repeat_relax.sh [--tol VALUE] ISIF1:IBRION1 ISIF2:IBRION2 ...

# Example: coarse ISIF=3 then fine ISIF=2
bash ~/scripts/structure/relax/multi_stage_repeat_relax.sh --tol 1e-6 3:2 2:2
```

Flags: `--tol VALUE` (default 1e-6), `--max-iter N` (default 50). The original
INCAR is restored automatically on exit. (Tolerance is now a flag, not the old
first positional argument.)

---

### `compare_poscar_contcar.sh`
Return `true`/`false` comparing POSCAR and CONTCAR numerically (relative
tolerance). Used by the relaxation loops; tolerance is an optional argument.

```bash
result=$(bash ~/scripts/structure/relax/compare_poscar_contcar.sh)       # default 1e-8
result=$(bash ~/scripts/structure/relax/compare_poscar_contcar.sh 1e-6)  # custom
```

> The former `compare_poscar_2_contcar.sh` was merged into this script.

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
bash ~/scripts/structure/phonons/fd_phonons_job.sh --no-submit   # write only
```

Flags `-n/--nodes -c/--cores -q/--queue -t/--time -a/--account` (defaults from
`lib/slurm_defaults.sh`), plus `--no-submit` to write the jobscript without
submitting. Header is generated via the shared lib.

---

### `batch_fd_jobs.sh`
Run `fd_phonons_job.sh` for every `POSCAR*/` subdirectory.

```bash
bash ~/scripts/structure/phonons/batch_fd_jobs.sh
```

Prompts for SLURM resources once and applies them to all directories.

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
bash ~/scripts/structure/elastic/setup.sh --dim 2D
```

Requires `~/input_files/vaspkit/elastic_INPUT.in` template. Flag: `--dim 3D|2D`
(default 3D). Validates POSCAR, vaspkit, and the template up front.

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
bash ~/scripts/structure/elastic/analysis.sh --dim 2D
```

Flag: `--dim 3D|2D` (default 3D).

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
bash ~/scripts/structure/scaled/directory_restructure.sh --dry-run --verbose  # preview
bash ~/scripts/structure/scaled/directory_restructure.sh                       # live run
```

Flags: `-n/--dry-run`, `-v/--verbose`, `-h/--help` (the `DRY_RUN=1`/`VERBOSE=1`
env vars still work too).

---

### `vary_inplane/setup_vary_inplane.sh`
Build the t-CuO AFII **vary_inplane** tree of re-runnable, CHGCAR-seeded VASP
decks. For each in-plane scale it lays out two disjoint c-axis chains that trace
the metastable orbital branches, seeding each from an extreme where the branch is
unambiguous:

- **compressed** (d_z²): z ascending `0.80 → 1.00`, seed at z=0.80
- **elongated** (d_x²−y²): z descending `1.30 → 1.01`, seed at z=1.30

The chain's first dir gets `INCAR.seed` (ICHARG=2, cold start); every later dir
gets `INCAR.prop` (ICHARG=1, reads the CHGCAR copied forward by the chain
jobscript). Structures are scaled from `POSCAR_ref` with `poscar_scaler.py`; the
per-scale `jobscript_compressed`/`jobscript_elongated` are delegated to
`write_chain_vasp_jobscript.sh` (via its `--out`/`--name` flags).

```bash
# assets live beside the script: POSCAR_ref, INCAR.seed, INCAR.prop, KPOINTS, POTCAR
bash ~/scripts/structure/scaled/vary_inplane/setup_vary_inplane.sh -y            # full 11-scale tree
bash ~/scripts/structure/scaled/vary_inplane/setup_vary_inplane.sh -y \
    --scales "1.0" --out ./test_build                                            # single scale
bash ~/scripts/structure/scaled/vary_inplane/setup_vary_inplane.sh -y --no-jobscripts
```

Flags: `--scales SPEC`, `--zc SPEC`, `--ze SPEC` (each a list `"a b c"` or range
`start:stop:step`), `--out DIR` (default `./vary_inplane_rebuild`), `--time
HH:MM:SS` (chain walltime), `--no-jobscripts` (decks only), `-y/--yes`, `-h`.
Dir names (`vary_inplane_lattice_scale_<s>/POSCAR_z_<z>/`) match the
`data_parser.sh` convention. rsync `--out` to `$WORK`, then `sbatch
jobscript_compressed jobscript_elongated` in each scale dir.

---

## structure/editor/

### `poscar_scaler.py`
Scale POSCAR lattice vectors. Three subcommands (merges the old
`poscar_scaler.py` + `scaling_poscar.py`); run with no args for interactive mode.
Shared POSCAR math lives in `poscar_lib.py`.

```bash
# Interactive
python3 ~/scripts/structure/editor/poscar_scaler.py

# single: 1 (uniform) or 3 (anisotropic) factors, optional -o OUTPUT
python3 ~/scripts/structure/editor/poscar_scaler.py single POSCAR 1.02
python3 ~/scripts/structure/editor/poscar_scaler.py single POSCAR 1.02 1.0 0.98 -o OUT

# grid: per-axis "lo hi step" ranges -> all combinations
python3 ~/scripts/structure/editor/poscar_scaler.py grid POSCAR \
    --x 0.95 1.05 0.01 --y 0.95 1.05 0.01 --z 0.95 1.05 0.01 --prefix run

# batch: read factor lines ("sx [sy sz]") from a file
python3 ~/scripts/structure/editor/poscar_scaler.py batch POSCAR factors.txt
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
python3 ~/scripts/structure/editor/change_scaling_factors.py X Y Z          # edits ./POSCAR
python3 ~/scripts/structure/editor/change_scaling_factors.py X Y Z -f FILE  # edits FILE
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
python3 ~/scripts/structure/editor/check_scaling.py --tol 1e-4 -r REF_POSCAR
```

Flags: `-t/--tol` (length tolerance Å, default 1e-3), `-r/--reference` (default POSCAR).

---

### `super_cell_maker.sh`
Generate phonopy supercells for all `POSCAR_*/` subdirectories, inject
MAGMOM if present, and replace POSCAR with SPOSCAR.

```bash
# Run from the directory containing POSCAR_*/ subdirectories
bash ~/scripts/structure/editor/super_cell_maker.sh          # prompts for X Y Z
bash ~/scripts/structure/editor/super_cell_maker.sh 2 2 2    # or pass them
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

### `util/benchmarks/bench_INCAR.sh`
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

### `util/batch_calcs/follow_up_calculations.sh`
Set up a follow-up calculation from an existing set of POSCAR_* directories,
optionally varying INCAR parameters (single param or a 2-param Cartesian grid).

```bash
bash ~/scripts/util/batch_calcs/follow_up_calculations.sh
```

> The earlier `follow_up_calc.sh` was merged into this enhanced version.

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

These live in **`lib/slurm_defaults.sh`** as `VASP_*` variables and are sourced
by every job-generating script. Override them per-run with a flag, by exporting
the variable (e.g. `VASP_QUEUE=development bash ...`), or permanently by editing
that one file.

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
