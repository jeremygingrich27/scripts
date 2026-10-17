# phonon_downhill: pseudocode (top-level loop)

Goal: starting from a relaxed t-CuO phase, follow unstable phonons downhill until a structure has no
unstable phonons. Each step below is meant to be one small script; the wrapper only calls them in order.

`<CHOICE: ...>` = open decision, Jeremy to set.

## Inputs
- start structure: a relaxed POSCAR (axially compressed or axially elongated), with its INCAR/KPOINTS/POTCAR/MAGMOM
- round = 0

## Loop

```
WHILE true:

  1. RELAX  (skip in round 0: the start structure is already relaxed)
     settings (decided 2026-10-16): ISIF = 3, a and b clamped (LATTICE_CONSTRAINTS), only c + ions free;
                                    ISYM = 2 (symmetrise to the group VASP finds in the displaced cell)
       a,b clamped at the START cell's own values (decided 2026-10-16), carried unchanged through every round
         (compressed 8.9439 A, elongated 7.9241 A supercell); so round 0 needs no relax
       <CHECK: LATTICE_CONSTRAINTS syntax/polarity never confirmed (relax_c README sec. 2/9);
               verify a,b unchanged after every round, halt if they moved>
     repeat: restart from CONTCAR
       until a round is converged within its FIRST ionic step (Pulay stress removed)
     check Cu moments kept the AFII signs (onsite matrices vs MAGMOM)
       if not: STOP that branch and flag why (no findsym, no phonons)

  2. SYMMETRY
     run findsym WITH the MAGMOM moments on the relaxed CONTCAR -> round_N.cif (magnetic group, BNS label)
       (decided 2026-10-16) one tight tolerance: 1e-3 A
     moments given to findsym along c (decided 2026-10-16)
     the .cif is the RECORD; the phonons use the relaxed CONTCAR as is
       (decided 2026-10-16, reversing "feeds next round": the relax ran with ISYM = 2, so the CONTCAR is
        already symmetric, and converting findsym's setting back to the cell was the fragile part)

  3. PHONONS
     set up phonopy supercell + displacements on the relaxed structure (MAGMOM carried over)
     run the displacement single points
     build force constants with --fc-calc traditional (symfc projector ignores MAGMOM)
       (decided 2026-10-16) DIM = 1 1 1 on the 64-atom cell (same as now);
       DISPLACEMENT_DISTANCE = 0.01 A, phonopy's default +/- handling (same as now);
       stability judged on the cell's commensurate modes only (crystal modes on the full FC matrix,
       no interpolated mesh). Displacement count will grow as symmetry drops (~40 min per displaced cell).

  4. FIND UNSTABLE MODES
     list modes with frequency below threshold, with irrep labels (crystal modes --basis)
       (decided 2026-10-16) unstable = frequency below -0.1 THz (acoustic modes are exactly 0 with --asr)
     if none: DONE, this structure is the result -> exit loop

  5. PICK MODE(S) + DIRECTION(S)
     for the chosen unstable multiplet, list the inequivalent directions
     (e.g. one arm vs two arms, Pmma vs Pnma; +u vs -u if they are not equivalent)
       (decided 2026-10-16) modes: LOWEST multiplet only for now; keep mode selection a separate option
         (e.g. lowest | all) so it can be extended to every unstable multiplet later
       directions: ALL inequivalent ISOTROPY directions of that multiplet, each its own scan
       sign: scan +u and -u unless the magnetic group makes them equivalent
       (decided 2026-10-16) BRANCH: every direction's minimum goes on to its own relax -> findsym -> phonons
         (a tree; each branch runs the loop independently until it has no unstable modes or is stopped)

  6. SCAN DOWNHILL  (per direction)
     displace atoms along the pattern at increasing amplitude u
     single-point energy at each u, check moments at each u
     keep going until E(u) turns back up (minimum bracketed)
       (decided 2026-10-16) extend: fixed step, keep adding points until E(u) has risen for N points past the lowest
       locate: polynomial fit near the bottom, then ONE check single point at the fitted u; it must be lower
         than its grid neighbours
       round 0 starts fresh (the 2026-10-12 freeze scans are not reused)
       N = 3 points must rise past the lowest before the scan stops
       fit: general quartic (odd terms allowed) to the lowest point + 2 neighbours each side
       if the check point is NOT lower than its neighbours: use the lowest grid point and continue
       step: fixed 0.02 A in amplitude (largest single-atom displacement) for every mode
         (decided 2026-10-16; curvature-set step dropped: it gives smaller steps to steeper modes,
          which are the ones with far-away minima)
     structure at the minimum -> start structure for the next round

  round += 1
  (back to 1. RELAX with the minimum structure)
```

## Output layout (decided 2026-10-16): nested, the path is the history
```
<phase>/                          e.g. pbe_AFII_compressed/
  round_0/
    phonons/                      phonopy run + mode list (start cell is already relaxed)
    scan_<irrep>-<direction>/     E(u) points, fit, check point, minimum
      round_1/
        relax/                    relaxation rounds + final CONTCAR
        round_1.cif               findsym (magnetic) result
        phonons/
        scan_<irrep>-<direction>/
          round_2/ ...
    scan_<irrep>-<direction>/
      round_1/ ...
```
- a summary line per round: space group, energy, lowest phonon, mode followed
