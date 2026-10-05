# QE convergence toolkit

A small set of single-purpose scripts to set up and run Quantum ESPRESSO
(`pw.x`) convergence studies. Python generators write the inputs; a bash wrapper
ties them together; one bash script writes a SLURM jobscript (TACC/`ibrun`) and
another runs the sweeps interactively (e.g. aflowlib/`mpirun`).

**Scope:** `ibrav = 0` inputs with an explicit `CELL_PARAMETERS` block and
`ATOMIC_POSITIONS` in `crystal` coordinates. Anything else is rejected up front
— this keeps the code free of Bravais-lattice / `celldm` special cases.

## What it does

- **ecut sweep** — one subdirectory per `ecutwfc`.
- **k-mesh sweep** — one subdirectory per mesh; cubic, or cell-aware
  anisotropic (`--kratio auto`, denser along the short axes).
- **scf or vc-relax** versions of either sweep (`--mode`).
- **Iterative vc-relax** — in relax mode each case is re-run, always feeding the
  relaxed structure back in, until re-relaxing it no longer moves the cell *or*
  the atoms (within thresholds). This removes Pulay stress: a single vc-relax
  uses a plane-wave basis frozen at the *starting* cell, so its result is only
  trustworthy once a re-relaxation under its own basis reproduces it.

The generators only *write inputs*; `pw.x` is run by the jobscript / runner.

## Layout you run it from

```
run_dir/
├── scf.in        # base template: ibrav=0, CELL_PARAMETERS, ATOMIC_POSITIONS (crystal), K_POINTS
└── pseudos/      # the .upf files, once — shared by every generated case
```

The generators write sweep subdirectories into `run_dir/` and pin each case's
`pseudo_dir` to the **absolute** path of this single `pseudos/` (nothing is
copied):

```
run_dir/
├── ecut_relax_sweep/ecut_60Ry/scf.in   ...
└── kpt_relax_sweep/mesh_10x10x2/scf.in ...
```

## Files

| File | Role |
|------|------|
| `qe_input.py` | Shared helpers — the only module that knows QE input syntax: read/set namelist keys, get/set `CELL_PARAMETERS` and `ATOMIC_POSITIONS`, set `K_POINTS`, force `pseudo_dir`, and `make_relax` (turn an scf input into a vc-relax input). |
| `qe_output.py` | Parse the relaxed cell (Å), positions (crystal) and energy from a finished vc-relax output. |
| `gen_ecut.py` | scf ecut sweep → `ecut_sweep/ecut_<E>Ry/`. |
| `gen_kpoints.py` | scf k-mesh sweep → `kpt_sweep/mesh_<A>x<B>x<C>/`. |
| `gen_ecut_relax.py` | vc-relax ecut sweep → `ecut_relax_sweep/...`. |
| `gen_kpoints_relax.py` | vc-relax k-mesh sweep → `kpt_relax_sweep/...`. `--kz K` (slabs) holds kz at K and sets the in-plane mesh from a1, a2 only. |
| `update_structure.py` | One reiteration cycle: compare `scf.in` to its `scf.out`, always write the relaxed structure back into `scf.in`, and decide converged (exit 0) / run again (exit 1) / no result (exit 2). |
| `setup_convergence.sh` | Wrapper: superset of the generators' arguments; builds the requested sweeps. |
| `plot_adatom_sites.py` | Scatter the adatom positions found under a directory over the slab's top layer, as a placement check -> `<dir>/adatom_sites.png`. |
| `gen_pp_slab.py` | pp.x / average.x inputs for one finished slab run: xy charge-density cuts at heights above each face, plus plane-averaged rho(z) and V(z) profiles, and a `run_pp.sh` -> `<case>/pp/`. |
| `gen_pair_curve.py` | pw.x scf inputs for an interaction curve of two atoms or two rigid molecules in a vacuum box (one input per separation), or a single-atom reference -> `<outdir>/<pair>/d_<sep>A/scf.in`. |
| `harvest_pair_curves.py` | Harvest the pair-curve trees into `<functional>/curve_data/`: per-pair tables (both spin starts, chosen lower state, E_bind vs isolated atoms, E vs 12 A, flags), atom references, and a summary with d_min and interaction ranges. |
| `build_slab.py` | Cut an N-bilayer slab along c from a relaxed bilayer-stacked bulk (wurtzite, 6H-SiC) and write one pw.x input: orientation, vacuum, dipole correction, relax region, spin, U. |
| `reorient_rocksalt.py` | Rewrite a rocksalt bulk (fcc primitive or conventional) so a3 is along [001] (conventional a×a×a cube) or [111] (hexagonal, a/√2 in-plane, 6 atoms); k-mesh rescaled to the bulk's spacing. Reorient only, no slab. |
| `build_rocksalt_slab.py` | Cut an N-plane slab from a reoriented rocksalt bulk and write one pw.x input (settings copied from the bulk): (001) nonpolar, (111) symmetric odd-N or stoichiometric polar even-N; supercell, vacuum, relax region, automatic dipole correction. |
| `make_jobscript.sh` | Writes a SLURM jobscript (TACC) that loops over the sweep dirs and runs `ibrun pw.x` (with the iterative-relax loop in relax mode). |
| `run_aflowlib.sh` | Runs the same sweeps interactively with `mpirun` — for machines with no scheduler/modules (e.g. aflowlib). |
| `pick_converged.py` | Read a relax sweep and report the *coarsest* ecut / k-mesh whose cell matches the densest case within tolerance (the cheapest converged setting). `--bare` prints just the value for shell capture. |
| `gen_final.py` | Write `final/relax.in` (tight vc-relax) + `final/scf.in` (scf for phonons) at a chosen ecut + mesh, seeded from a converged structure. |
| `make_deposition.py` | Interactive: build adatom deposition inputs from a slab `scf.in` -> `<element>/<nospin\|spin>/h<H>/xy_<x>_<y>/`. |
| `apply_structure.py` | Copy the cell + positions from one pw.x input into another (carries the relaxed geometry from `relax.in` into `scf.in` at run time). |
| `qe2poscar.py` | Write a VASP `POSCAR` from a pw.x input (default `./scf.in` -> `./POSCAR`) for viewing in VESTA; crystal positions -> Direct, others -> Cartesian Å; `Cu1`/`Cu2`-style labels kept as separate groups. `--from-out scf.out` uses the last final coordinates of a relax/vc-relax (cell from the output if printed, else from the input). |
| `gen_ph.py` | Write the phonon inputs: `ph.in` (DFPT q-grid), `q2r.in` (force constants), and — given a `--kpath` file — `matdyn.in` (dispersion). |
| `setup_phonon.sh` | Wrapper: pick the converged ecut/mesh, then build the whole `final/` directory (`gen_final.py` + `gen_ph.py`). |
| `make_jobscript.sh` (phonon: `make_phonon_jobscript.sh`) | `make_phonon_jobscript.sh` writes a one-shot jobscript: iterative tight vc-relax → scf → ph.x → q2r.x → matdyn.x, each step guarded on the previous reaching `JOB DONE`. |

## Install: one copy, on PATH

There is exactly one copy of this toolkit per machine; do not copy it into run
directories.

| Machine | Location |
|---|---|
| local | `~/scripts/qe_scripts` |
| Lonestar6 | `$HOME/scripts/qe_scripts` |

Put the directory itself on PATH (in `~/.bashrc`), so every script is callable
by name from any run dir:

```bash
export PATH="$HOME/scripts/qe_scripts:$PATH"
```

Do not symlink the `.sh` scripts elsewhere: they find their sibling scripts
through their own location (`HERE=...BASH_SOURCE`), which a symlink would
point at the wrong directory. Generated jobscripts record this directory as
`QE_SCRIPTS` and call `update_structure.py` / `apply_structure.py` from it at
run time, so editing the toolkit while jobs are queued changes what they run.

Local and LS6 are kept in sync by copying the directory up (`rsync -av
~/scripts/qe_scripts/ ls6:scripts/qe_scripts/`).

## Quick start — TACC (SLURM)

From `run_dir/` (with `scf.in` + `pseudos/`), with the toolkit on PATH:

```bash
# 1. create the sweep directories (vc-relax, anisotropic k-mesh for a long-c cell)
setup_convergence.sh --mode relax \
    --ecuts "60 70 80 90" --kn "2 4 6" --kratio auto --cell-dofree all

# 2. generate the jobscript (the ibrun line is written verbatim into it)
make_jobscript.sh --mode relax --account PHY24018 \
    --ibrun "ibrun pw.x -npool 8"

# 3. submit
sbatch jobscript
```

For a plain scf convergence (cheaper; converge energy/forces before relaxing),
use `--mode scf` in both steps. Drop `--kratio auto` for cubic cells (e.g. ScN).

## Quick start — interactive (aflowlib / no scheduler)

```bash
cd ~/qe_test/ScN                 # toolkit on PATH, as above
setup_convergence.sh --mode relax --ecuts "60 80" --kn "4 6"
run_aflowlib.sh      --mode relax --np 4
```

`run_aflowlib.sh` loops over the same sweep dirs, launching `mpirun -np <N> pw.x`
and driving the same reiteration loop. Options: `--mode`, `--np`, `--pw`,
`--dirs`, `--max-iter`, `--cell-thr/--angle-thr/--pos-thr`.

## Phonon workflow (ph.x), after convergence

Once the convergence sweeps have finished, build and run a full
relax→scf→phonon-dispersion workflow from the same run dir (which holds
`ecut_relax_sweep/`, `kpt_relax_sweep/`, and `pseudos/`):

```bash
# 1. pick the converged ecut/mesh and build final/ (relax.in, scf.in, ph.in,
#    q2r.in, matdyn.in). --nq is the phonon q-grid; --kpath is your band path.
setup_phonon.sh --nq "4 4 4" --occupations smearing --kpath kpath.dat  # metal/smeared
setup_phonon.sh --nq "4 4 1" --epsil --kpath kpath.dat                 # insulator (LO-TO)

# 2. write the one-shot jobscript and submit
make_phonon_jobscript.sh --account PHY24018 \
    --pw "ibrun pw.x -npool 4 -pd .true." --ph "ibrun ph.x -npool 4"
sbatch jobscript.ph
```

The jobscript runs, in `final/` and all sharing one `ESPRESSO_TMPDIR`: a tight
iterative vc-relax (`relax.in`, tight `conv_thr`/`forc_conv_thr`/`etot_conv_thr`
so residual stress doesn't leak into the phonons) → copy the relaxed geometry
into `scf.in` → scf → `ph.x` → `q2r.x` → `matdyn.x`. Each step runs only if the
previous reached `JOB DONE`.

**The band path is yours to supply.** A correct high-symmetry path needs
Bravais-lattice knowledge, which this toolkit deliberately stays out of (the
`ibrav=0`, no-`celldm` rule). `--kpath` takes a file with one `qx qy qz npts`
line per point (crystal coords by default; `--kpath-cartesian` for 2π/a) — the
same idea as a phonopy `HIGH_SYMMETRY_POINTS` file. Without `--kpath`, `ph.in`
and `q2r.in` are still written; only `matdyn.in` is skipped.

Use `--epsil` for insulators (adds the dielectric tensor + Born charges for
LO-TO splitting); leave it off for metals / smeared systems, where `ph.x`
handles the occupations automatically.

**Occupations.** `relax.in` and `scf.in` in `final/` get `occupations='fixed'`
by default, whatever the sweeps used (`--occupations` on `setup_phonon.sh`,
passed to `gen_final.py`). The sweeps use smearing for robustness, but a
smeared insulator makes `ph.x` classify it as a metal and refuse `epsil` (this
crashed the first 6H-SiC phonon runs). Choices: `fixed` (insulators), `smearing`
(gaussian, 0.004 Ry; call `gen_final.py --smearing/--degauss` directly for other
values), `inherit` (keep the seed's scheme). DFT+U systems cannot use `epsil` in
`ph.x` regardless, which is why ScN kept smearing and no `epsil`.

## `setup_convergence.sh`

| Option | Default | Meaning |
|--------|---------|---------|
| `--input` | `scf.in` | Base template. |
| `--pseudos` | `pseudos` | Dir of `.upf` files (its absolute path is written into each case). |
| `--mode` | `scf` | `scf` or `relax` (selects the scf vs vc-relax generators). |
| `--ecuts` | — | e.g. `"60 70 80 90"`; builds the ecut sweep if given. |
| `--kn` | — | e.g. `"2 4 6"`; builds the k-mesh sweep if given. |
| `--kratio` | `1 1 1` | `auto` (∝ 1/\|aᵢ\|), `1 1 1` (cubic), or three numbers. `N` labels the longest axis. |
| `--cell-dofree` | `all` | vc-relax cell DOF (relax mode): `all`, `ibrav`, `shape`, `volume`, … |
| `--press` | — | Target pressure in kbar (relax mode). |

The individual generators (`gen_*.py`) accept the same flags and can be run
directly; `-h` on any of them prints its options.

## `make_jobscript.sh`

| Option | Default | Meaning |
|--------|---------|---------|
| `--mode` | `scf` | `scf` (one pw.x per case) or `relax` (iterative vc-relax loop). |
| `--ibrun` | `ibrun pw.x` | Launch command, written **verbatim** into the jobscript (e.g. `"ibrun pw.x -npool 8"`). |
| `--dirs` | mode-dependent | Glob(s) the jobscript loops over (default matches the generators' output dirs). |
| `--account` `--nodes` `--ntasks` `--queue` `--time` `--jobname` | TACC-ish defaults | SLURM header. |
| `--modules` | `intel/19.1.1 impi/19.0.9 qe` | `module load` line. |
| `--scratch` | `$SCRATCH/qe_tmp/$SLURM_JOB_ID` | Root for QE's temp/`outdir` (see *Storage* below); written literally so it expands in-job. |
| `--max-iter` | `5` | Max vc-relax reiterations per case (relax mode; must be ≥ 2). |
| `--cell-thr` `--angle-thr` `--pos-thr` | `0.01` Å / `0.05`° / `0.01` Å | Convergence thresholds passed to `update_structure.py`. |
| `--scripts` | this dir | Where the jobscript finds `update_structure.py` at run time. |
| `--out` | `jobscript` | Output filename. |

The generated jobscript uses **`module reset`, not `module purge`** — on TACC
`module purge` removes the module that provides `ibrun`, after which every
`pw.x` call dies with `ibrun: command not found`.

## Storage: `$WORK` vs `$SCRATCH`

The templates intentionally have **no `outdir`** in `&CONTROL`. QE then takes
`outdir` from the `ESPRESSO_TMPDIR` environment variable (else the current
directory). This lets the run scripts place QE's heavy temporary I/O
(wavefunctions, charge density, restart files) wherever the machine prefers,
without baking a path into every input:

- **`make_jobscript.sh`** sets a unique `ESPRESSO_TMPDIR` per case under
  `--scratch` (default `$SCRATCH/qe_tmp/$SLURM_JOB_ID/<case>`), so heavy I/O
  lands on `$SCRATCH` while `scf.in`/`scf.out` and the sweep tree stay in
  `$WORK`. Purge `$SCRATCH/qe_tmp` after jobs finish.
- **`run_aflowlib.sh`** points `ESPRESSO_TMPDIR` at a local `./out` per case.

## Reiterative vc-relax

Every pass is kept: after pass N the jobscript copies `scf.in` -> `scf.in.iterN` (the input that
pass ran) and `scf.out` -> `scf.out.iterN` (amendment 2026-10-05). The final `scf.in`/`scf.out`
are unchanged, so `harvest_convergence.py` is unaffected.

In relax mode the run loop does, per case:

```bash
for i in $(seq 1 $MAXITER); do
    ibrun pw.x -npool 8 < scf.in > scf.out
    python3 update_structure.py scf.in scf.out --iter $i \
        --cell-thr 0.01 --angle-thr 0.05 --pos-thr 0.01
    rc=$?
    [ $rc -eq 0 ] && break    # self-consistent: converged
    [ $rc -eq 2 ] && break    # run did not finish: stop this case
    # rc == 1: relaxed structure written back into scf.in, run again
done
```

`update_structure.py` compares the relaxed `scf.out` structure to the `scf.in`
that produced it — convergence needs the lattice constants (a/b/c), angles
(α/β/γ) **and** every atom's displacement (minimum-image, in Å) within the
thresholds. Two important behaviors:

- It **always** writes the relaxed cell + positions back into `scf.in`, so
  `scf.in` always holds the latest relaxed geometry (the converged structure
  ends up in `scf.in`, no need to dig it out of `scf.out`).
- It will **not** converge before `--min-iter` (default **2**), even if the
  first pass is already within tolerance. This forces at least one re-relaxation
  of the relaxed structure under its own basis — the step that actually removes
  Pulay stress. The run loop passes the current iteration via `--iter`.

So a fresh case takes at least two iterations: relax from the guess → feed back
→ re-relax to confirm.

## DFT+U

Use the new `HUBBARD` card (QE ≥ 7.1), **not** the old `lda_plus_u` /
`Hubbard_U(i)` `&SYSTEM` keywords (which abort with *"DFT+Hubbard input syntax
has changed since v7.1"*). Example, U = 2.9 eV on the Sc 3d shell:

```
HUBBARD (atomic)
U Sc-3d 2.9
```

placed after the other cards. The card rides through all generators untouched.

## Validation runs (Lonestar6, `qe/7.3`)

The toolkit was validated with iterative vc-relax sweeps on two systems × two
functionals (ScN with `U Sc-3d 2.9`; 6H-SiC). All 26 cases converged; results
matched experiment and the expected PBE/PBEsol trend (PBEsol gives smaller `a`).
Full tables are in `../HANDOFF.md`. Converged settings:

| System | ecut | k-mesh | PBE | PBEsol |
|--------|------|--------|-----|--------|
| ScN (FCC, conventional `a`) | 80 Ry | 6×6×6 | `a` = 4.574 Å | `a` = 4.525 Å |
| 6H-SiC (hex, `a`/`c`) | 80 Ry | 10×10×2 (5:1 via `--kratio auto`) | 3.095 / 15.184 Å | 3.079 / 15.108 Å |

`a`/`c` are converged to ≤0.001 Å at these settings (80→90 Ry shifts `a` by
≤0.0005 Å; ScN needs 6×6×6, 6H-SiC is mesh-insensitive). The converged structure
of each case is written back into its `scf.in` by `update_structure.py`.

## Surface deposition (`make_deposition.py`)

Builds the inputs for an adatom energy surface. Run it **inside** the directory
holding the slab `scf.in`; it asks what to deposit and writes one input per
case. Inputs only; `pw.x` is run by the jobscript as usual.

```
$ cd my_slab_dir && make_deposition.py
cell            9.022 x 9.022 x 33.533 A
substrate period 4.511 x 4.511 A
top layer at z = 23.533 A, vacuum 19.999 A, 112 atoms
adatom element Sc/N [Sc]:
spin (none/spin/both) [none]: both
heights in A, space separated [1 2 3]:
wedge region (1/16 irreducible, 1/8 with duplicate checks) [1/16]:
wedge grid spacing in A [0.564]:
dipole correction (y/n) [y]:
```

Tree:

```
<element>/<nospin|spin>/h<height>/xy_<x>_<y>/scf.in
```

**Scope:** `ibrav=0` with an explicit `CELL_PARAMETERS` block, an orthorhombic
cell with `c` along z, `ATOMIC_POSITIONS` in `crystal`, and a square substrate
period. The cell is used **as given**: to study a lower coverage, hand it a
slab that is already a supercell.

**The wedge is built on the substrate period, not the cell.** The script finds
the shortest axis-aligned translations that map the whole slab onto itself
(4.511 Å for ScN(001), whether the cell is 4.511 or 9.022 Å) and lays a uniform
grid over the symmetry wedge of *that* square. So the same points come out
whatever supercell you hand it, and they all sit in one tile.

| Prompt | Meaning |
|--------|---------|
| adatom element | must already be in `ATOMIC_SPECIES` |
| spin | `none`, `spin`, or `both`; with spin the adatom becomes its own species (`Sc1`, same `.upf`) so `starting_magnetization` (0.3) applies to it and not to the slab atoms of the same element |
| heights | Å above the topmost nuclear plane |
| wedge region | `1/16` = the irreducible triangle atop_N -> atop_Sc -> hollow; `1/8` = that plus its mirror image, whose points duplicate the first half and check the symmetry |
| wedge grid spacing | Å; rounded to an even number of divisions of the period, and the count is reported |
| dipole correction | `tefield`/`dipfield`/`edir=3`/`eamp=0` with `emaxpos`/`eopreg` computed so the sawtooth's drop region straddles the middle of the vacuum |

**Checking the placements:** `plot_adatom_sites.py [DIR]` walks DIR for
`scf.in` files, takes the highest-z atom in each as the adatom, and scatters
those positions over the slab's top layer, writing `DIR/adatom_sites.png`. A
file whose top plane holds more than one atom (the bare slab template) has no
adatom and is skipped.

### Irreducible wedge of ScN(001)

The ideal slab has 16 in-plane symmetry operations: 4mm about an atom column,
each also with a (1/2,1/2) translation, since the primitive surface cell is the
3.19 Å one and the 4.511 Å cell is its (sqrt2 x sqrt2)R45 supercell. A general
point therefore has 16 images, so the irreducible region is 1/16 of the square
cell (= 1/8 of the primitive cell): the right triangle atop_N (0,0) ->
atop_Sc (0.5,0) -> hollow (0.25,0.25), with the right angle at the hollow. At
0.564 Å spacing that region holds 9 points, and the `1/8` option holds 15 (the
same 9 plus 6 mirror duplicates). The run summary names each point
(`atop_N`, `bridge`, `hollow`, or `-` for a general position) from the geometry
itself, so a wrongly placed point shows up immediately.

**Energy reference.** A binding curve referenced to a far-separation height in
the *same* cell cancels cell, cutoff and mesh. An absolute adsorption energy
needs a separate reference run (isolated spin-polarised atom in a box, or bulk
Sc / 1/2 E(N2)); neither is generated here.

**Note on `qe_input.py`:** `make_deposition.py` carries its own `ATOMIC_SPECIES`
/ `ATOMIC_POSITIONS` reader and writer. The shared ones read exactly `nat`
contiguous rows (slab templates often have blank lines grouping the species) and
rewrite rows in place, which breaks as soon as the atom count grows. The shared
module is left untouched so the convergence scripts are unaffected.

## Slab charge-density cuts (`gen_pp_slab.py`)

Writes pp.x / average.x inputs for ONE finished slab calculation (built from
pseudocode signed off 2026-10-03). Run it after the SCF: it refuses without a
finished `CASE_DIR/scf.out`, because average.x's `npt` is the FFT grid along z
read from it. Geometry comes from the final coordinates in `scf.out` when present
(relax), else from `scf.in`.

```
gen_pp_slab.py CASE_DIR --awin-ang 2.531 [--heights "1 2 3 4 5 6"] [--nx 100 --ny 173]
```

Tree written under `CASE_DIR/pp/`:

```
profiles/rho/      pp.in (plot_num=0, cube, extracts 'rho' once)  average.in
profiles/vbare_h/  pp.in (plot_num=11, cube)                       average.in
cuts/<face>_<elements>/h<h>A/pp.in   2D cut, reads ../../../profiles/rho/rho
run_pp.sh          runs profiles/rho first, then the potential, then the cuts
```

- pp.x needs `e1` ⟂ `e2` (in alat units). Rectangular cells use (a1, a2);
  hexagonal cells (120°) use the a × √3a rectangle (a1+a2, a2−a1). Defaults
  nx=100, ny=173 give equal spacing on the hexagonal window; use `--ny 100` for
  a square cell.
- Heights are measured from the outermost atomic plane on each face; the face
  label lists every element in that plane (e.g. `top_Si`, `top_N-Sc`).
- Warns if a cut falls in the dipole sawtooth region or past mid-vacuum.
- `--awin-ang` is required (average.x macroscopic window, e.g. one bulk layer
  period); the planar-average column does not depend on it.
- `--spin-density` (nspin=2 runs only) also writes the spin polarization: `profiles/magn`
  (plot_num=6) and a `pp_magn.in` -> `cut_magn.dat` next to every cut.
- `run_pp.sh` needs `ESPRESSO_TMPDIR` pointing at the SCF's temp dir
  (`$SCRATCH/qe_tmp/<jobid>/<case>` for toolkit jobscripts); launchers
  overridable with `PPX` / `AVGX`.

## Pair interaction curves (`gen_pair_curve.py`)

Vacuum curves that bound how far apart adatoms (and their periodic images) must
be. Built from pseudocode signed off 2026-10-03. Inputs only.

```
gen_pair_curve.py --pair Sc,N --pseudos pseudos --grid "0.8:3.0:0.05,3.0:12.0:0.25" \
                  --hubbard "Sc-3d 5.0 ortho-atomic"
gen_pair_curve.py --molecule N2 --bond 1.11 --orientation parallel|collinear --pseudos pseudos --grid ...
gen_pair_curve.py --atom Sc --pseudos pseudos            # isolated-atom reference
```

- Box `--box "30 20 20"` (A), pair axis along x, motif centred. `--grid` is
  comma-separated `start:stop:step` segments; duplicates at the joins are dropped.
- Every input: scf, nspin=2, `starting_magnetization` = `--start-mag` (0.5) on
  every species, gaussian smearing `--degauss` (0.01), conv_thr 1e-8,
  mixing_beta 0.4, ecut 100, single Gamma point as `K_POINTS automatic 1 1 1`
  (NOT `K_POINTS gamma`: QE 7.3 refuses ortho-atomic Hubbard with the Gamma-only
  trick, error in orthoUwfc). `pseudo_dir` is the absolute path
  of `--pseudos`, so generate on the machine that runs the cases.
- `--hubbard "<El>-<shell> <U> <projector>"` adds a HUBBARD card only to cases
  that contain that element.
- Skips (and reports) separations where two atoms would be < 0.8 A apart, or
  where less than 9 A of vacuum separates the motif from its image along x.
- Masses come from a small table in the script (`MASSES`); add an element there
  if it refuses.
- `--spin-starts parallel,antiparallel` writes both starting arrangements under
  `<pair>/<parallel|antiparallel>/d_<sep>A/` (keep the lower energy per point).
  Antiparallel gives partner B `-start-mag`; a same-element partner becomes
  species `<El>1` (same .upf), and the HUBBARD card lists it too.
  `--electron-maxstep` sets `electron_maxstep`. Open-shell pairs at
  intermediate distances need damping: the Sc-N dev test at 6 A oscillated
  around 1e-5 Ry for 40 iterations at mixing_beta 0.4 (fix used:
  `--mixing-beta 0.2 --electron-maxstep 300`).

## Slab builder (`build_slab.py`)

One slab per call (signed-off pseudocode, 2026-10-03); loop it in shell for a
case tree.

```
build_slab.py --bulk BULK_DIR --bilayers 8 --orientation up|down --ecut 122 \
              --kmesh "10 10" --pseudos pseudos --out case/scf.in \
              [--vacuum 20] [--relax-free 2] [--spin 0.5] [--hubbard "Ga-3d 3.9 ortho-atomic"]
```

- Bulk from `BULK_DIR/scf.out` final coordinates (vc-relax), else `scf.in`;
  a3 must be along z.
- Bilayers are found from the alternating short/long vertical gaps; the slab is
  cut through the long gaps (one broken bond per surface atom). It refuses if
  the gaps do not alternate or a bilayer is not cation + anion.
- `up` keeps the bulk orientation (GaN: Ga face up, +z = [0001]; SiC: Si face
  up); `down` mirrors z.
- `--relax-free F`: outer F bilayers per side free (calculation='relax'); 0 =
  plain scf. `--spin S`: nspin 2 with starting_magnetization S on every species.
- `--occupations smearing` (default; gaussian `--degauss`, 0.01) or `fixed`;
  dipole correction always on (sawtooth mid-vacuum, via
  `make_deposition.add_dipole`); `pseudo_dir` absolute.
- Masses come from `MASSES` in `gen_pair_curve.py`.

## Rocksalt reorientation (`reorient_rocksalt.py`)

Signed-off pseudocode, 2026-10-05. Reorients the bulk only; the slab cut is a
separate step.

```
reorient_rocksalt.py --bulk BULK_DIR --face 001|111 --out OUT_DIR/scf.in
```

- Geometry from `BULK_DIR/scf.out` final coordinates, else `scf.in` (same
  reader as `build_slab.py`); namelists, species and U copied from `scf.in`.
- Cube axes are found from the six nearest neighbours, so the input may be the
  2-atom fcc cell, the 8-atom cube, or a rotated cell.
- `001`: conventional cube, 2+2 atoms per layer, layers a/2 apart.
  `111`: a1 = a/2[1-10], a2 = a/2[01-1], a3 = a[111]; alternating pure-cation /
  pure-anion planes a/(2√3) apart, ABC stacked (a polar face).
- a1 along x, a3 along z. K-mesh: n_i = ceil(|b_i| / dk), dk = the bulk's finest
  |b_j| / n_j (never coarser than the bulk).
- Refuses unless both input and output are rocksalt (6 opposite-species
  neighbours at a/2), the atom count matches the volume, and volume per f.u. is
  unchanged. Prints the layer list.

## Rocksalt slab builder (`build_rocksalt_slab.py`)

Signed-off pseudocode, 2026-10-05. One slab per call; takes the output of
`reorient_rocksalt.py`.

```
build_rocksalt_slab.py --bulk BULK_DIR --layers N --pseudos pseudos --out CASE/scf.in \
                       [--bottom Sc|N] [--supercell "n m"] [--vacuum 20] \
                       [--relax-free F] [--dipole auto|on|off]
```

- Planes are atoms sharing a z (within 0.05 A). (001): every plane is
  stoichiometric. (111): pure cation / anion planes; `--bottom` is required and
  picks the bottom species. Odd N gives the same termination on both sides
  (non-stoichiometric, symmetric); even N gives a stoichiometric polar slab.
- `--dipole auto` turns the sawtooth correction on only when the slab is not
  symmetric under z -> -z (mirror or inversion, up to an in-plane shift), i.e.
  (111) even N.
- Settings (ecut, U, smearing, species) are copied from `BULK_DIR/scf.in`;
  `pseudo_dir` = absolute `--pseudos`. K-mesh = bulk in-plane mesh / supercell
  (rounded up), kz = 1.
- `--relax-free F`: outer F planes per side free (calculation='relax'); 0 = scf.
- Prints the plane list, composition, symmetry and dipole state.

## Harvesting pair curves (`harvest_pair_curves.py`)

Signed-off pseudocode, 2026-10-03. No plotting.

```
harvest_pair_curves.py [FUNC_DIR ...] [--tols "10 5 1"]      # default: cwd
```

- A case is OK only with `JOB DONE`, a final "convergence has been achieved" and
  no "convergence NOT achieved"; everything else is FAIL with its reason.
- Per separation: both starts' energies and total moments, the lower OK one is
  chosen. `E_bind = E_chosen - sum(isolated atoms)` (eV, from `atom_<El>/`),
  `E_rel12 = E_chosen - E_chosen(largest d)` (eV). Flags: SWITCH, SINGLE, NONE.
- Interaction range for tolerance t (meV): the smallest d from which every OK
  point has |E_rel12| < t.
- d_min: lowest grid point and the vertex of the parabola through it and its
  neighbours. On an asymmetric (Morse-like) well the parabola leans slightly to
  the soft side (+0.002 A on a 0.05 A grid in the synthetic test).
- Output `FUNC_DIR/curve_data/`: `<pair>.dat`, `atom_refs.dat`, `summary.dat`,
  rebuilt whole on every run.

## Troubleshooting

**`ibrun: command not found`** — the jobscript used `module purge` instead of
`module reset`; `purge` removes the TACC module that provides `ibrun`. The
generated jobscripts use `module reset`, so this only bites if you hand-edit.

**`DFT+Hubbard input syntax has changed since v7.1`** — the input still uses the
old `lda_plus_u` / `Hubbard_U(i)` keywords. Switch to the `HUBBARD` card (see
*DFT+U* above).

**`fft_type_set (6): there are processes with no planes. Use pencil
decomposition (-pd .true.)`** — too many MPI ranks for a small cell: the FFT
grid has fewer real-space planes than ranks-per-pool, so some ranks get none.
Common for tiny cells (e.g. 2-atom ScN) on a full 128-core node. Fixes, in
order of preference:

- Add **`-pd .true.`** to the launcher — pencil (2D) FFT decomposition spreads
  the grid across many ranks: `--ibrun "ibrun pw.x -npool 4 -pd .true."`. This
  is QE's own suggested fix and works regardless of cell size.
- Run on **fewer ranks** for small cells: `--ntasks 32` (or 16). More efficient
  than 128 ranks on a 2-atom cell; the node is still billed in full on the
  node-exclusive queues, but the run is clean and fast.
- Use **more k-point pools** (`-npool 8`) so each pool has fewer ranks — but
  `-npool` is capped by the irreducible k-point count of the *smallest* mesh in
  the sweep, so keep `-pd .true.` as well.

Larger cells (e.g. 12-atom 6H-SiC with a long c-axis) have bigger FFT grids and
rarely hit this, but `-pd .true.` is harmless to leave on everywhere.

## Requirements

- `pw.x` on PATH at run time (TACC: via the `qe` module; aflowlib: already in
  `/usr/local/bin`). QE ≥ 7.1 for the `HUBBARD` card.
- `python3` (standard library only — no numpy/scipy).
- Input: `ibrav = 0` with `CELL_PARAMETERS`, `ATOMIC_POSITIONS (crystal)`,
  `nat`, and a `K_POINTS` card; **no `outdir`** (set via `ESPRESSO_TMPDIR`).
