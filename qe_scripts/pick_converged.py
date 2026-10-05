#!/usr/bin/env python3
"""pick_converged.py — choose the coarsest converged setting from a relax sweep.

Reads every <sweep>/<case>/scf.in (each already holds its relaxed cell, written
back by update_structure.py), computes the lattice constants, and reports the
*coarsest* setting whose cell agrees with the densest case within tolerance —
i.e. the cheapest setting that is already converged.

The sweep type is detected from the case directory names the generators write,
so nothing here is system-specific:
  ecut_<E>Ry        -> ecut sweep;  the knob is ecutwfc (Ry)
  mesh_<A>x<B>x<C>  -> k-mesh sweep; the knob is the automatic mesh

Density ordering: ecut by its Ry value, meshes by the product A*B*C. The densest
case is the reference; the first case (ascending density) whose a,b,c are within
--tol and whose angles are within --angle-tol is chosen. If none qualify (sweep
not yet converged), the densest case is returned and a warning printed.

    python3 pick_converged.py ecut_relax_sweep
    python3 pick_converged.py kpt_relax_sweep --tol 0.001 --bare

--bare prints only the chosen knob to stdout ("80" or "6 6 6"), for a wrapper to
capture; the human-readable table always goes to stderr.
"""

import argparse
import glob
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import qe_output as qo
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import qe_output as qo


def _ecut_of(label):
    m = re.fullmatch(r"ecut_(\d+(?:\.\d+)?)Ry", label)
    return m.group(1) if m else None


def _mesh_of(label):
    m = re.fullmatch(r"mesh_(\d+)x(\d+)x(\d+)", label)
    return tuple(int(x) for x in m.groups()) if m else None


def _collect(sweep):
    """Return (kind, [(density, label, knob, lattice_constants), ...]).

    kind is 'ecut' or 'mesh'; knob is the bare value to print for that case."""
    rows, kind = [], None
    for path in sorted(glob.glob(os.path.join(sweep, "*", "scf.in"))):
        label = os.path.basename(os.path.dirname(path))
        ecut, mesh = _ecut_of(label), _mesh_of(label)
        if ecut is not None:
            this, density, knob = "ecut", float(ecut), ecut
        elif mesh is not None:
            this, density, knob = "mesh", mesh[0] * mesh[1] * mesh[2], \
                "{} {} {}".format(*mesh)
        else:
            continue  # not a recognized case dir
        if kind and this != kind:
            raise SystemExit(f"{sweep}: mixed sweep types (ecut and mesh cases)")
        kind = this
        lc = qo.lattice_constants(qi.get_cell(qi.read_input(path)))
        rows.append((density, label, knob, lc))
    if not rows:
        raise SystemExit(f"{sweep}: no ecut_<E>Ry or mesh_<A>x<B>x<C> cases found")
    rows.sort(key=lambda r: r[0])
    return kind, rows


def pick(sweep, tol, angle_tol):
    """Return (kind, rows, ref_lc, chosen_row, converged_bool)."""
    kind, rows = _collect(sweep)
    ref = rows[-1][3]                      # densest case = reference
    for row in rows:
        lc = row[3]
        d_len = max(abs(lc[i] - ref[i]) for i in range(3))
        d_ang = max(abs(lc[i] - ref[i]) for i in range(3, 6))
        if d_len < tol and d_ang < angle_tol:
            return kind, rows, ref, row, True
    return kind, rows, ref, rows[-1], False   # nothing converged -> densest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sweep", help="a relax sweep dir (ecut_relax_sweep / kpt_relax_sweep)")
    p.add_argument("--tol", type=float, default=0.001,
                   help="max |Δa/b/c| vs the densest case, in angstrom (default 0.001)")
    p.add_argument("--angle-tol", type=float, default=0.05,
                   help="max |Δα/β/γ| vs the densest case, in degrees (default 0.05)")
    p.add_argument("--bare", action="store_true",
                   help="print only the chosen knob to stdout (for shell capture)")
    args = p.parse_args(argv)

    kind, rows, ref, chosen, converged = pick(args.sweep, args.tol, args.angle_tol)

    knob_hdr = "ecut(Ry)" if kind == "ecut" else "mesh"
    print(f"  {'case':16s} {knob_hdr:>10s}   a       b       c      (Å)", file=sys.stderr)
    for _d, label, knob, lc in rows:
        mark = "  <- chosen" if label == chosen[1] else ""
        print("  {:16s} {:>10s}  {:7.4f} {:7.4f} {:7.4f}{}".format(
            label, knob, lc[0], lc[1], lc[2], mark), file=sys.stderr)
    if not converged:
        print(f"  WARNING: no case within tol={args.tol} Å of the densest — "
              f"sweep not converged; returning densest case.", file=sys.stderr)

    print(chosen[2] if args.bare else f"{kind} = {chosen[2]}")


if __name__ == "__main__":
    main()
