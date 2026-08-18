# Scripts user-friendliness refactor — progress tracker

Goal: make the VASP scripts in this folder more user-friendly. Working one
folder at a time; this file is the source of truth so work can resume across
sessions without re-deriving context.

## Agreed scope (from the user)
1. **Help text + usage** — every script gets `-h/--help` and a usage block.
2. **Scriptable** — interactive-only scripts gain CLI flags (prompts kept as
   fallback); add `-y/--yes` for fully non-interactive runs where it makes sense.
3. **Error handling + validation** — `set -euo pipefail`, validate args/files,
   clear messages via the shared `die`/`need_file`/`need_cmd`/`confirm` helpers.
4. **Consistent SLURM config** — all job generators source
   `lib/slurm_defaults.sh` instead of hardcoding account/queue/nodes/modules.

Interface policy: **free to refactor** (flag names, prompts, output may change
for consistency).

## Conventions (established in jobs/)
- `lib/slurm_defaults.sh` holds `VASP_*` defaults (overridable via env) plus
  `vasp_slurm_header` and the `die/need_file/need_cmd/confirm` helpers.
- Scripts locate the lib relative to themselves:
  `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; source "${SCRIPT_DIR}/../lib/slurm_defaults.sh"`
- Flag style: short+long (`-n/--cores`), `${2:?--flag needs a value}` guards,
  unknown flag → error + usage. `-h/--help` always exits 0.
- Scripts that *submit* jobs must confirm first (no silent auto-`sbatch`).

## Folder status

### lib/  ✅ done
- [x] `slurm_defaults.sh` — NEW shared config + header + helpers.

### jobs/  ✅ done (tested, README updated)
- [x] `write_jobscript.sh` — refactored (reference implementation).
- [x] `write_chain_vasp_jobscript.sh` — flags (`--dirs/--copy`), SLURM flags, lib, `--submit`.
- [x] `scaled_batch_basic.sh` — flags, dead code removed, auto-submit gated behind `--submit`.
- [x] `elastic_vaspkit.sh` — lib, flags, auto-submit gated.
- [x] `submit_jobs.sh` — NEW, merges submit_multiple.sh + submit_job_loop.sh (`--name`, `-r`, `-y`).
      (submit_multiple.sh and submit_job_loop.sh deleted.)
- [x] `additional_functions/` snippets — added one-line purpose header to each
      (not standalone, so no flags/help).

### magnetism/  ✅ done (tested, README updated)
- [x] Merged `coplanar_magnetic_atoms.py` + `coplanar_magnetic_ordering.py`
      (~95% duplicate) into NEW `coplanar_magmom.py`: argparse (`-h`),
      interactive fallback, `-M/--moment` (±M) and `--pn P N` modes. Originals deleted.
- Python conventions settled: argparse with optional positionals + tty-aware
  interactive fallback; `die()` to stderr; same flag style as the shell scripts.
### structure/phonons/  ✅ done (tested, README updated)
- [x] `fd_phonons_job.sh` — sources lib + vasp_slurm_header, proper usage(),
      flags from lib defaults, added `--no-submit` (submits by default — it's a
      submit tool used in batch).
- [x] `make_disp_line_arg.sh` — env shebang, set -euo, `-h`.
- [x] `make_disp_interactive.sh` — added `-h`, absolute SCRIPT_DIR.
- [x] `batch_fd_jobs.sh` — env shebang, set -euo, `-h`, lib-default prompts,
      uses SCRIPT_DIR (not hardcoded path).
- [x] `after_relax.sh` — env shebang, set -uo, `-h` (keeps true/false output).
- [x] `vasp_fd_batch_prep.sh` — env shebang, set -uo, `-h`, validation.
- [x] `setup_varied_phonons.sh` — `-h`, set -uo; collapsed a TRIPLE
      energy_minima.py call per subdir into one.
- [x] `fd_phonons_job_line_arg.sh` — left as-is (clean thin wrapper).
- DELETED `batch_disp.sh` (duplicate of make_disp_interactive.sh AND had a broken
  `~/scripts/phonons/...` path — missing `structure/`).

### structure/elastic/  ✅ done (tested, README updated)
- [x] `setup.sh` — fixed shebang (/usr/bin/bash → env), set -euo, lib, `-h`,
      `--dim` flag, validates POSCAR/vaspkit/template.
- [x] `analysis.sh` — same treatment (`--dim`, validation).
- [x] `scaled_analysis.sh` — `-h`, set -uo, validation, passes args through to
      analysis.sh, continues on per-dir failure.
- [x] `distribute_inputs.sh` — added `-h` (already had set -euo + arg handling).
- [x] `collect_info.sh` — added `-h` (already robust).

### structure/editor/  ✅ done (tested, README updated)
- [x] NEW `poscar_lib.py` — shared POSCAR helpers (read/write/scale_lattice/
      fmt_tag/lattice_lengths/cell_volume); removes duplication.
- [x] `poscar_scaler.py` — MERGED with `scaling_poscar.py`; argparse subcommands
      single/grid/batch + interactive. `scaling_poscar.py` deleted.
- [x] `ca_ratio_volume_constant.py` — argparse, uses poscar_lib (volume-preserving
      c/a verified: 64→64 Å³).
- [x] `volume.py` — argparse, uses poscar_lib.
- [x] `change_scaling_factors.py` — argparse, added `-f/--file`.
- [x] `check_scaling.py` — argparse, added `-t/--tol` and `-r/--reference`.
- [x] `loop_scale_factor_changer.sh` — `-h`, set -euo, validation.
- [x] `loop_over_inplane_lattice_constants.sh` — `-h`, set -euo, validation.
- [x] `super_cell_maker.sh` — `-h`, accepts X Y Z as args, fixed undeclared
      `default_moments` array bug.
- [x] `setup_varied_scale_factors.sh` — left as-is (already has help/flags/
      interactive/coupling).
### structure/elastic/  — not started
### structure/phonons/  — not started
### structure/relax/  ✅ done (tested with a fake VASP toolchain, README updated)
- [x] `compare_poscar_contcar.sh` — merged in the better `_2_` logic (optional
      tolerance arg, relative comparison). `compare_poscar_2_contcar.sh` deleted.
- [x] `setup.sh` — flags (`--incar/--name/-f`), lib helpers, keeps positional dir
      (additional_functions snippets still call it that way).
- [x] `repeat_relax.sh` — flags (`--max-iter/--tol/--no-kpoints`), lib, ibrun
      detection, fixed compare-tolerance call, checkpoint/resume kept.
- [x] `multi_stage_repeat_relax.sh` — `--tol/--max-iter` flags (tol no longer a
      positional), lib, fixed compare call, INCAR-restore trap kept.
- BUG FIXED: multi_stage previously passed tolerance to the no-arg compare
  script, which ignored it — now compare takes the arg.
### structure/scaled/  ✅ done (tested, README updated)
- [x] `data_parser.sh` — already flag-driven/documented; **fixed CRLF line
      endings that made it fail to run** (`$'\r'` errors). Left logic as-is.
- [x] `directory_restructure.sh` — added `-n/--dry-run`, `-v/--verbose`, `-h`
      (env-var fallbacks kept).
- [x] `setup_system.sh` — fixed stale header name, added `usage()`/`-h`,
      validate KPR (number) and KSCHEME (int).
- [x] `data_parser_yes_relax.sh`, `interactive_data_parser.sh` — left as-is
      (already clean thin `exec` wrappers around data_parser.sh).
- Repo-wide: scanned for CRLF; only README.md + data_parser.sh had it, both
  normalized to LF. (Worth a quick CRLF check in remaining folders.)
### util/ (+ batch_calcs, benchmarks, templates)  ✅ done (tested, README updated)
- [x] `parse_data.sh` — already flag-driven; fixed stale header name only.
- [x] `parse_poscar.py`, `energy_minima.py` — argparse (`-h`); energy_minima also
      fixed deprecated pandas `delim_whitespace` → `sep=r"\s+"`.
- [x] `vasp_timer.sh`, `delete_WAVECAR.sh`, `generate_INCAR.sh`,
      `distribute_inputs.sh`, `sync_to_work.sh` — env shebang/set/`-h`
      (sync_to_work also asserts $WORK is set).
- [x] `collect_calcs.sh` — `-h`; added the vasprun.xml + XDATCAR excludes its
      header promised but omitted.
- [x] `crystal_system_directory_setup.sh` — env shebang, `-h`, usage(), KPR/KSCHEME validation.
- [x] `batch_calcs/basic_loop_cmd.sh` — `-h` (marked as a template).
- [x] `batch_calcs/follow_up_calculations.sh` — `-h`. DELETED the superseded
      `follow_up_calc.sh` (merged into this enhanced version).
- [x] `benchmarks/bench_INCAR.sh` — `-h` (already thorough otherwise).
- [x] Fixed README: bench_INCAR path (batch_calcs→benchmarks), follow_up merge.

## 🎉 ALL FOLDERS COMPLETE
Whole toolkit refactored. Remaining ideas if desired: convert the remaining
interactive-only generators to optional flags; add a top-level `bin/` on PATH.

## After each folder
- Update `README.md` usage blocks to match new flags.
- Re-run `bash -n` on every touched script.
