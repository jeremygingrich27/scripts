#!/usr/bin/env python3
"""update_structure.py — one cycle of an iterative vc-relax.

Compares the structure in an scf.in to the relaxed structure in its scf.out,
and ALWAYS writes the relaxed cell + positions back into scf.in so scf.in
always holds the latest relaxed geometry (and is the starting point for the
next run). Then:

  * converged -> exit 0: the cell (a/b/c, angles) AND every atom agree within
    the thresholds, AND this is at least iteration --min-iter (default 2). The
    min-iter requirement forces a relaxed structure to be re-relaxed under its
    OWN basis before being accepted, which removes residual Pulay stress (a
    single vc-relax uses a basis frozen at the *starting* cell); a structure
    that survives re-relaxation unchanged is genuinely self-consistent.
  * run again -> exit 1: still drifting, or within tolerance but iteration
    < min-iter (one confirming re-relaxation still owed).
  * no result -> exit 2: scf.out has no final coordinates (run did not finish);
    scf.in is left untouched.

Intended to be called inside the run loop, which passes the iteration index:

    for i in $(seq 1 $MAXITER); do
        ibrun pw.x < scf.in > scf.out
        python3 update_structure.py scf.in scf.out --iter $i; rc=$?
        [ $rc -eq 0 ] && break          # converged
        [ $rc -eq 2 ] && break          # run failed
    done                                # rc==1: run again

Cell is assumed in angstrom, atomic positions in crystal coordinates (the
toolkit's ibrav=0 convention). Because scf.in is always overwritten with the
relaxed structure, the converged geometry ends up in scf.in (and in scf.out's
final coordinates) — no need to hunt for it.
"""

import argparse
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import qe_output as qo
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import qe_output as qo

EXIT_CONVERGED = 0
EXIT_RUN_AGAIN = 1
EXIT_NO_RESULT = 2


def max_position_drift(in_atoms, out_atoms, cell):
    """Largest atom displacement (angstrom) between two fractional-coordinate
    sets, using the minimum-image convention and `cell` (angstrom)."""
    worst = 0.0
    for (s_in, f_in), (s_out, f_out) in zip(in_atoms, out_atoms):
        if s_in != s_out:
            raise ValueError(f"atom order changed: {s_in} vs {s_out}")
        df = [f_out[i] - f_in[i] for i in range(3)]
        df = [d - round(d) for d in df]                    # minimum image
        cart = [sum(df[j] * cell[j][i] for j in range(3)) for i in range(3)]
        worst = max(worst, qo.vlen(cart))
    return worst


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("infile", help="the scf.in that was run")
    p.add_argument("outfile", help="the scf.out it produced")
    p.add_argument("--cell-thr", type=float, default=0.01,
                   help="max |Δa/b/c| in angstrom (default 0.01)")
    p.add_argument("--angle-thr", type=float, default=0.05,
                   help="max |Δα/β/γ| in degrees (default 0.05)")
    p.add_argument("--pos-thr", type=float, default=0.01,
                   help="max atom displacement in angstrom (default 0.01)")
    p.add_argument("--iter", type=int, default=1,
                   help="current iteration index, from the run loop (default 1)")
    p.add_argument("--min-iter", type=int, default=2,
                   help="iterations required before convergence is accepted; "
                        ">=2 re-relaxes the relaxed structure to remove Pulay "
                        "stress (default 2)")
    args = p.parse_args(argv)

    in_text = qi.read_input(args.infile)
    with open(args.outfile) as fh:
        final = qo.parse_final_structure(fh.read())
    if final is None:
        print(f"  [update] no final coordinates in {args.outfile} — run did not finish")
        return EXIT_NO_RESULT

    in_cell = qi.get_cell(in_text)
    _, in_atoms = qi.get_positions(in_text)
    out_cell, out_atoms = final["cell"], final["atoms"]

    a0 = qo.lattice_constants(in_cell)
    a1 = qo.lattice_constants(out_cell)
    d_len = max(abs(a1[i] - a0[i]) for i in range(3))        # a, b, c
    d_ang = max(abs(a1[i] - a0[i]) for i in range(3, 6))     # alpha, beta, gamma
    d_pos = max_position_drift(in_atoms, out_atoms, out_cell)

    print(f"  [update] Δ(a,b,c)={d_len:.4f} A  Δ(angles)={d_ang:.4f} deg  "
          f"Δ(atoms)={d_pos:.4f} A")

    # Always capture the relaxed structure in scf.in (it is both the result and
    # the next iteration's starting point).
    new_text = qi.set_cell(in_text, out_cell)
    new_text = qi.set_positions(new_text, out_atoms)
    with open(args.infile, "w") as fh:
        fh.write(new_text)

    within = (d_len < args.cell_thr and d_ang < args.angle_thr
              and d_pos < args.pos_thr)
    if within and args.iter >= args.min_iter:
        print("  [update] structure self-consistent — converged")
        return EXIT_CONVERGED
    if within:
        print(f"  [update] within tolerance but iteration {args.iter} < "
              f"min {args.min_iter} — re-relaxing to confirm")
    else:
        print(f"  [update] still drifting — relaxed structure written back to "
              f"{args.infile}, run again")
    return EXIT_RUN_AGAIN


if __name__ == "__main__":
    sys.exit(main())
