# phonon_downhill

Downhill structure search for t-CuO by following unstable phonons:
relax -> findsym -> phonons -> unstable modes -> scan each direction to its minimum -> relax the minimum -> ...
until a structure has no unstable mode (STABLE) or a branch is stopped (STOPPED, with the reason).
**TACC does not allow `sbatch` from compute nodes**, so jobs never submit. A job does its VASP runs and the cheap
work that follows (phonon analysis, findsym, phonopy setup, new scan / round folders), then stops. The tree moves
on when `downhill.sh advance` is run on a login node (decided 2026-10-18: when Jeremy checks). Design and every
decision: `pseudocode.md`.

## Use

```bash
DH=$HOME/scripts/structure/phonon_downhill
$DH/downhill.sh init   PHASE_ROOT START_DIR NAME_PREFIX   # files only, submits nothing
$DH/downhill.sh advance PHASE_ROOT                        # login node: submit everything that is ready
$DH/downhill.sh status PHASE_ROOT                         # one line per round and scan, with job states
```

- `START_DIR`: the relaxed start cell. `POSCAR`, `MAGMOM` (phonopy format `MAGMOM = ...`), and the phonopy
  disp-run `INCAR`, `KPOINTS`, `POTCAR`.
- `NAME_PREFIX`: start of the job names, e.g. `tCuO-AFII-comp_pbe` -> `tCuO-AFII-comp_pbe_dh-r1-SM4-Pnma-relax`.
- `advance` is safe to repeat: a folder whose job (its `JOBID` file) is still queued or running is skipped, and
  work that ran out of walltime is simply submitted again (finished points / displacements are skipped).
- To stop a branch by hand: put a file `STOPPED` (with a reason) in its `round_N` folder; jobs already queued
  still run, but the driver will not go further there.

## Environment (LS6)

- python venv at `VENV` (downhill.conf) with numpy, pyyaml, spglib, **phonopy 4.5.0**, crystal-utilities.
  phonopy v4 moved setup (`-d`, `-f`) to `phonopy-init`; the scripts use that.
- ISOTROPY (`findsym`, `iso`) on PATH with ISODATA set (from ~/.bashrc; inherited by batch jobs).

## Tree on disk

```
PHASE_ROOT/
  inputs/            POSCAR (clamp reference), INCAR.sp, INCAR.relax, KPOINTS, POTCAR, MAGMOM, NAME_PREFIX
  round_0/
    POSCAR
    phonons/         disp-NNN/ runs, FORCE_CONSTANTS, modes.dat, crystal_modes/, SOFT_MODES,
                     multiplet.npz, directions/ (one .npy pattern per direction), directions.txt
    scan_<irrep>_<group>/
      start.POSCAR, pattern.npy, u_0.000/ u_0.020/ ..., check_u_<u>/, scan.dat
      round_1/
        POSCAR, SOURCE        (the scan minimum)
        relax/r01 r02 ...     CONTCAR_final, DONE
        symmetry/             findsym.in/.out/.cif, GROUP
        phonons/ ...
        scan_.../round_2/ ...
```
Marker files: `JOBID` (last job submitted for that folder), `COMPLETED` (a VASP run finished), `MOMENTS_LOST` (a scan point lost AFII),
`STABLE`, `STOPPED` (branch ended; the file says why), `relax/DONE`, `symmetry/DONE`, `phonons/FAILED`.
CHGCARs are moved to `$SCRATCH/phonon_downhill/<job id>/<run path>/` (`CHGCAR.location` in each run).

## The scripts

| script | does |
|---|---|
| `downhill.sh` | driver: init / next / advance / status; decides the next step of a round; submits only on a login node |
| `downhill.conf` | every setting, marked (J) Jeremy's decision or (C) Claude's default |
| `job_common.sh` | shared job functions: run VASP, move CHGCAR, walltime check, stop a branch |
| `job_relax.sh` | relax rounds until one converges in its first ionic step; STOPCAR before the walltime |
| `job_phonons.sh` | runs the phonopy displacements |
| `job_scan.sh` | one direction: steps u until the minimum is bracketed, check point, seeds the next round |
| `make_incars.py` | INCAR.sp / INCAR.relax from the disp-run INCAR (relax tags listed in it) |
| `setup_phonons.sh` | phonopy-init displacements (DIM 1 1 1, MAGMOM) + one VASP dir each |
| `analyse_phonons.sh` | FORCE_SETS, traditional FORCE_CONSTANTS, crystal-utilities labels, soft modes, directions |
| `soft_modes.py` | Gamma modes of the cell (ASR by projection), lowest multiplet below the threshold |
| `find_directions.py` | inequivalent directions in the multiplet from the magnetic group's action |
| `make_scan_point.py` | POSCAR(u) = start + u * pattern |
| `scan_status.py` | next scan action: NEXT / CHECK / MIN / NOMIN / HALT; writes scan.dat |
| `relax_check.py` | judge a relax round: CONVERGED / CONTINUE / HALT (a,b clamp) |
| `check_moments.py` | AFII signs and size from the LDAUPRINT occupation matrices |
| `symmetry_step.py` | findsym with moments along c -> .cif + GROUP |
| `dh_lib.py` | POSCAR / INCAR / OUTCAR helpers |

## Validation (2026-10-16, locally)

- `check_moments.py` = the hand awk on the freeze points.
- `soft_modes.py` = crystal modes to 1e-6 THz (both phases); FORCE_CONSTANTS from `analyse_phonons.sh` =
  the hand-built ones to 1e-14 eV/A^2; phonopy-init gives the same 4 displacements as the original set.
- `find_directions.py` finds exactly the hand directions: elongated X2- one-arm (Cmcm) + two-arm (P4/nmm),
  compressed SM4 Pmma + Pnma; overlap with the freeze-series patterns >= 0.9999.
- Dry run of the whole chain with a fake sbatch / VASP: round 0 phonons -> scans -> fit + check point ->
  round 1 relax (2 rounds) -> findsym -> 14-displacement phonon setup.
