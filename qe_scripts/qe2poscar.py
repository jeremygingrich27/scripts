#!/usr/bin/env python3
"""qe2poscar.py — write a VASP POSCAR from a pw.x input, for viewing in VESTA.

Run in a directory holding scf.in (or point it at any pw.x input):

    qe2poscar.py                    # ./scf.in  -> ./POSCAR
    qe2poscar.py relax.in -o RELAX.vasp

Requires ibrav=0 with an explicit CELL_PARAMETERS card (the toolkit
convention). Crystal positions are written as Direct; angstrom / bohr / alat
positions as Cartesian in angstrom.

POSCAR needs atoms grouped by species, so rows are regrouped by QE label in
order of first appearance. Labels such as Cu1/Cu2 (separate magnetic species)
stay separate groups but are written with the bare element name (Cu Cu O) so
VESTA recognises them; the original labels go in the comment line.

--from-out OUT (amendment signed off 2026-10-05) takes the geometry from the
LAST "Begin final coordinates" block of a relax / vc-relax output: positions
from that block; cell from the block if present (vc-relax), else from the input
(relax keeps the cell fixed). It refuses if OUT has no final coordinates.

    qe2poscar.py scf.in --from-out scf.out -o RELAXED.vasp
"""

import argparse
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import qe_output as qo
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)
    import qe_output as qo


def element(label):
    """Bare element symbol from a QE species label (Cu1, Fe_up, O2 -> Cu, Fe, O)."""
    m = re.match(r"[A-Z][a-z]?", label)
    return m.group(0) if m else label


def positions_for_poscar(text):
    """Return (mode, atoms): mode 'Direct' or 'Cartesian', atoms as
    (label, [x, y, z]) with Cartesian coordinates converted to angstrom."""
    unit, atoms = qi.get_positions(text)
    if unit == "crystal":
        return "Direct", atoms
    if unit == "angstrom":
        scale = 1.0
    elif unit == "alat" or unit == "":
        scale = qi.get_alat_angstrom(text)
        if scale is None:
            raise ValueError("ATOMIC_POSITIONS in alat but no celldm(1) or A set")
    elif unit == "bohr":
        scale = qi.BOHR_TO_ANG
    else:
        raise ValueError(f"unsupported ATOMIC_POSITIONS unit {unit!r}")
    return "Cartesian", [(s, [c * scale for c in xyz]) for s, xyz in atoms]


def final_geometry(out):
    """(cell or None, mode, atoms) from the last 'Begin final coordinates' block.
    cell is None when the block has no CELL_PARAMETERS (fixed-cell relax)."""
    if "Begin final coordinates" not in out:
        return None
    block = out.split("Begin final coordinates")[-1].split("End final coordinates")[0]
    cell = None
    cm = re.search(r"(?i)CELL_PARAMETERS\s*\(([^)]*)\)", block)
    if cm:
        scale = qo._cell_to_ang_scale(cm.group(1))
        rows = block[cm.end():].strip().splitlines()[:3]
        cell = [[float(x) * scale for x in r.split()[:3]] for r in rows]
    pm = re.search(r"(?i)ATOMIC_POSITIONS\s*\(([^)]*)\)", block)
    if not pm:
        return None
    unit = pm.group(1).strip().lower()
    atoms = []
    for line in block[pm.end():].strip().splitlines():
        parts = line.split()
        if len(parts) < 4 or not re.match(r"[A-Za-z]", parts[0]):
            break
        atoms.append((parts[0], [float(x) for x in parts[1:4]]))
    if unit == "crystal":
        return cell, "Direct", atoms
    if unit == "angstrom":
        return cell, "Cartesian", atoms
    if unit == "bohr":
        return cell, "Cartesian", [(s, [c * qi.BOHR_TO_ANG for c in xyz]) for s, xyz in atoms]
    raise ValueError(f"unsupported final ATOMIC_POSITIONS unit {unit!r}")


def poscar_text(text, comment, final=None):
    cell = qi.get_cell_angstrom(text)
    if final is not None:
        fcell, mode, atoms = final
        cell = fcell if fcell is not None else cell
    else:
        mode, atoms = positions_for_poscar(text)

    labels = list(dict.fromkeys(s for s, _ in atoms))   # first-appearance order
    groups = {lab: [xyz for s, xyz in atoms if s == lab] for lab in labels}

    out = [f"{comment}  [{' '.join(labels)}]", "1.0"]
    out += ["  {:18.12f} {:18.12f} {:18.12f}".format(*v) for v in cell]
    out.append("  " + " ".join(f"{element(lab):>4s}" for lab in labels))
    out.append("  " + " ".join(f"{len(groups[lab]):>4d}" for lab in labels))
    out.append(mode)
    for lab in labels:
        out += ["  {:18.12f} {:18.12f} {:18.12f}  {}".format(*xyz, lab)
                for xyz in groups[lab]]
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", default="scf.in",
                   help="pw.x input to read (default: scf.in)")
    p.add_argument("-o", "--output", default=None,
                   help="POSCAR to write (default: POSCAR next to the input)")
    p.add_argument("--from-out", default=None,
                   help="relax/vc-relax output: use its final coordinates (cell too, if printed)")
    args = p.parse_args(argv)

    out_path = args.output or os.path.join(os.path.dirname(args.input), "POSCAR")
    text = qi.read_input(args.input)
    final = None
    comment = f"from {os.path.abspath(args.input)}"
    if args.from_out:
        final = final_geometry(open(args.from_out).read())
        if final is None:
            sys.exit(f"{args.from_out}: no final coordinates (relax did not finish)")
        comment = f"final coordinates of {os.path.abspath(args.from_out)}"
    with open(out_path, "w") as fh:
        fh.write(poscar_text(text, comment, final))
    src = args.from_out or args.input
    print(f"  [qe2poscar] {src} -> {out_path}")


if __name__ == "__main__":
    sys.exit(main())
