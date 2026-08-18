#!/usr/bin/env python3
"""subcell_extract.py — pull the smaller repeating cell out of a supercell.

The inverse of `POSCAR.repeat(nx, ny, nz)`: divides each lattice vector by the
given integer and keeps the atoms in the first sub-block. Useful when a
supercell exists only to carry a magnetic ordering and you want the underlying
crystallographic cell back for a non-magnetic run.

Only checks that the atom count divides correctly, not that the supercell is
genuinely periodic on the sub-block — pass --verify for that (needs numpy; the
space group also needs spglib).

Examples
--------
  subcell_extract.py POSCAR --div 2 2 2 -o POSCAR_conv
  subcell_extract.py POSCAR --div 2 2 2 -o POSCAR_conv --verify --title "t-CuO conv"
"""
import os
import sys
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poscar_lib as pl


def extract(st, div, tol=1e-6):
    """Return the sub-cell structure dict. `div` is a 3-list of ints."""
    div = np.asarray(div, dtype=float)
    frac = st["frac"] % 1.0
    u = (frac * div) % div
    u[u > div - tol] -= div[None, :].repeat(len(u), 0)[u > div - tol]
    keep = np.all(u < 1.0 - tol, axis=1)

    counts, sel = [], []
    start = 0
    for c in st["counts"]:
        idx = np.where(keep[start:start + c])[0] + start
        counts.append(len(idx))
        sel.append(idx)
        start += c
    order = np.concatenate(sel) if sel else np.array([], dtype=int)

    return {"comment": st["comment"],
            "cell": st["cell"] / div[:, None],
            "species": list(st["species"]),
            "counts": counts,
            "frac": np.clip(u[order], 0.0, None)}


def verify(orig, sub, div):
    """Report composition and lattice; check that repeating reproduces orig."""
    a, b, c = np.linalg.norm(sub["cell"], axis=1)
    comp = "  ".join(f"{s}{n}" for s, n in zip(sub["species"], sub["counts"]))
    print(f"    {comp} = {sum(sub['counts'])} atoms   "
          f"a={a:.4f} b={b:.4f} c={c:.4f}  c/a={c / a:.4f}")

    n_ok = sum(sub["counts"]) * int(np.prod(div)) == sum(orig["counts"])
    cell_ok = np.allclose(sub["cell"] * np.asarray(div, float)[:, None], orig["cell"])
    print(f"    atom count x{int(np.prod(div))} matches: {n_ok}    "
          f"lattice x{tuple(div)} matches: {cell_ok}")

    try:
        import spglib
    except ImportError:
        return
    ds = spglib.get_symmetry_dataset(
        (sub["cell"], sub["frac"], _numbers(sub)), symprec=1e-4)
    print(f"    space group: {ds.international} (#{ds.number})")


def _numbers(st):
    from itertools import chain
    return list(chain.from_iterable(
        [i + 1] * n for i, n in enumerate(st["counts"])))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("poscar")
    p.add_argument("--div", nargs=3, type=int, required=True,
                   metavar=("NX", "NY", "NZ"), help="supercell multiples to undo")
    p.add_argument("-o", "--out", help="output POSCAR (default: <input>_sub)")
    p.add_argument("--title", help="replace the POSCAR comment line")
    p.add_argument("--tol", type=float, default=1e-6, help="fractional tolerance")
    p.add_argument("--verify", action="store_true",
                   help="report composition, lattice and space group")
    args = p.parse_args()

    st = pl.read_structure(args.poscar)
    sub = extract(st, args.div, args.tol)
    if args.title:
        sub["comment"] = args.title

    expected = sum(st["counts"]) / np.prod(args.div)
    if sum(sub["counts"]) != expected:
        sys.exit(f"ERROR: kept {sum(sub['counts'])} atoms, expected {expected:g} — "
                 f"{args.poscar} is not a clean {'x'.join(map(str, args.div))} supercell")

    out = args.out or f"{args.poscar}_sub"
    pl.write_structure(out, sub)
    print(f"Written: {out}")
    if args.verify:
        verify(st, sub, args.div)


if __name__ == "__main__":
    main()
