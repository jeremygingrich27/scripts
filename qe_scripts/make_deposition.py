#!/usr/bin/env python3
"""make_deposition.py — build adatom deposition inputs from a slab scf.in.

Run it inside a directory holding the slab input:

    cd my_slab_dir && python3 make_deposition.py

It reads the cell from `scf.in`, works out the substrate's in-plane period,
asks what to deposit and where, and writes one ready-to-run input per case:

    <element>/<nospin|spin>/h<height>/xy_<x>_<y>/scf.in

Heights are Angstrom above the topmost nuclear plane of the slab. The xy
points are a uniform grid over the symmetry-irreducible wedge of the surface,
built on the *substrate* period rather than the cell, so handing it a 2x2
supercell gives the same wedge as the 1x1 it was built from.

Scope (checked up front): ibrav=0 with an explicit CELL_PARAMETERS block, an
orthorhombic cell with c along z, ATOMIC_POSITIONS in `crystal`, and a square
substrate period (as for rocksalt (001)).

Replaces gen_adatom.py, whose flags this asks for interactively instead.
"""

import math
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
except ImportError:
    import qe_input as qi                # run directly by path (its dir is on sys.path)


def fmt_height(h):
    """1.0 -> '1.0', 2.25 -> '2.25' for directory names."""
    s = "{:.3f}".format(h).rstrip("0")
    return s + "0" if s.endswith(".") else s


LAYER_TOL_ANG = 0.5      # atoms within this of the top plane are the top layer
VACUUM_WARN_ANG = 10.0   # warn below this much vacuum left above the adatom
START_MAG = 0.3          # starting_magnetization for the adatom species
EOPREG_MAX = 0.1         # sawtooth drop region, as a fraction of c
SITE_TOL_ANG = 0.1       # how close counts as "on top of" an atom
CARD_RE = re.compile(r"(?i)^\s*(ATOMIC_|CELL_|K_POINTS|OCCUPATIONS|CONSTRAINTS|"
                     r"HUBBARD|ADDITIONAL_K_POINTS|SOLVENTS)")


# --------------------------------------------------------------------------
#  Reading and writing the cards qe_input does not cover
# --------------------------------------------------------------------------
def _find_card(lines, name):
    for i, ln in enumerate(lines):
        if re.match(rf"(?i)^\s*{name}\b", ln):
            return i
    raise ValueError(f"no {name} card found in scf.in")


def _card_rows(lines, start, parse):
    """Rows after a card header, skipping blank lines, stopping at the next
    card. Returns (rows, index of the last row)."""
    rows, last = [], start
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if not ln.strip():
            continue
        if CARD_RE.match(ln) or ln.lstrip().startswith("&"):
            break
        row = parse(ln)
        if row is None:
            break
        rows.append(row)
        last = i
    return rows, last


def _species_row(ln):
    parts = ln.split()
    if len(parts) < 3:
        return None
    try:
        return (parts[0], float(parts[1]), parts[2])
    except ValueError:
        return None


def _atom_row(ln):
    parts = ln.split()
    if len(parts) < 4:
        return None
    try:
        return (parts[0], [float(parts[1]), float(parts[2]), float(parts[3])],
                parts[4:])
    except ValueError:
        return None


def get_species(text):
    """[(label, mass, pseudopotential), ...] from ATOMIC_SPECIES."""
    lines = text.splitlines()
    rows, _ = _card_rows(lines, _find_card(lines, "ATOMIC_SPECIES"), _species_row)
    return rows


def set_species(text, species):
    lines = text.splitlines()
    head = _find_card(lines, "ATOMIC_SPECIES")
    _, last = _card_rows(lines, head, _species_row)
    rows = ["  {:3s} {:12.6f}  {}".format(lab, mass, upf) for lab, mass, upf in species]
    return "\n".join(lines[:head + 1] + rows + lines[last + 1:]) + "\n"


def get_atoms(text):
    """(unit, [(label, [x, y, z], trailing if_pos flags), ...])."""
    lines = text.splitlines()
    head = _find_card(lines, "ATOMIC_POSITIONS")
    unit = re.match(r"(?i)^\s*ATOMIC_POSITIONS\b\s*[\(\{]?\s*([a-z_]*)",
                    lines[head]).group(1).lower()
    rows, _ = _card_rows(lines, head, _atom_row)
    nat = qi.get_key(text, "nat")
    if nat is not None and int(nat) != len(rows):
        raise ValueError(f"nat = {nat} but {len(rows)} position rows were read")
    return unit, rows


def set_atoms(text, atoms):
    """Replace the whole ATOMIC_POSITIONS block, so it can grow."""
    lines = text.splitlines()
    head = _find_card(lines, "ATOMIC_POSITIONS")
    _, last = _card_rows(lines, head, _atom_row)
    rows = []
    for lab, xyz, extras in atoms:
        row = "  {:3s} {:18.12f} {:18.12f} {:18.12f}".format(lab, *xyz)
        if extras:
            row += "  " + " ".join(extras)
        rows.append(row)
    return "\n".join(lines[:head + 1] + rows + lines[last + 1:]) + "\n"


# --------------------------------------------------------------------------
#  Geometry
# --------------------------------------------------------------------------
def check_cell(cell):
    """Require an orthorhombic cell with c along z; return (a, b, c)."""
    off = [abs(cell[i][j]) for i in range(3) for j in range(3) if i != j]
    if max(off) > 1e-6:
        raise ValueError("cell is not orthorhombic; a, b, c must lie along x, y, z")
    return cell[0][0], cell[1][1], cell[2][2]


def _wrap(d):
    """Fractional separation into (-0.5, 0.5]."""
    d -= math.floor(d)
    return d - 1.0 if d > 0.5 else d


def top_layer(atoms, c):
    """(top fractional z, the atoms within LAYER_TOL_ANG of it)."""
    ztop = max(at[1][2] for at in atoms)
    tol = LAYER_TOL_ANG / c
    return ztop, [at for at in atoms if ztop - at[1][2] < tol]


def _is_translation(atoms, tx, ty):
    """True if shifting every atom by (tx, ty) reproduces the structure."""
    for lab, (fx, fy, fz), _e in atoms:
        if not any(lab2 == lab and abs(fz2 - fz) < 1e-6
                   and abs(_wrap(fx + tx - fx2)) < 1e-4
                   and abs(_wrap(fy + ty - fy2)) < 1e-4
                   for lab2, (fx2, fy2, fz2), _e2 in atoms):
            return False
    return True


def substrate_period(atoms, layer, a, b):
    """Shortest axis-aligned in-plane periods of the slab, in Angstrom.

    A supercell of a surface still repeats at the underlying period, and the
    symmetry wedge belongs to that period, not to the cell."""
    def shortest(axis):
        ref = layer[0]
        cands = set()
        for lab, (fx, fy, _fz), _e in layer:
            if lab != ref[0]:
                continue
            d = (fx - ref[1][0]) if axis == 0 else (fy - ref[1][1])
            other = (fy - ref[1][1]) if axis == 0 else (fx - ref[1][0])
            if abs(_wrap(other)) < 1e-4:
                d = d % 1.0
                if d > 1e-6:
                    cands.add(round(d, 6))
        for d in sorted(cands):
            if _is_translation(atoms, d if axis == 0 else 0.0,
                               0.0 if axis == 0 else d):
                return d
        return 1.0

    return shortest(0) * a, shortest(1) * b


def site_label(xy, layer, a, b, c):
    """Name a point from the top-layer atoms nearest to it.

    Being equidistant from two atoms is not enough to be a bridge: every point
    on their perpendicular bisector is. The point must also sit *between* them,
    which is what the vector sum tests."""
    near = []
    for lab, (fx, fy, _fz), _e in layer:
        dx, dy = _wrap(fx - xy[0]) * a, _wrap(fy - xy[1]) * b
        near.append((math.hypot(dx, dy), lab, dx, dy))
    near.sort()
    d1, lab1 = near[0][0], near[0][1]
    if d1 < SITE_TOL_ANG:
        return f"atop_{lab1}"
    tied = [n for n in near if abs(n[0] - d1) < SITE_TOL_ANG]
    sx = sum(n[2] for n in tied)
    sy = sum(n[3] for n in tied)
    if math.hypot(sx, sy) > SITE_TOL_ANG:        # not centred on them
        return "-"
    return {2: "bridge", 4: "hollow"}.get(len(tied), "-")


def wedge_points(period_a, period_b, spacing, region):
    """Uniform grid over the symmetry wedge of a square surface period.

    Returns fractional coordinates of the *period*, so (0.25, 0.25) is the
    four-fold hollow whatever the cell size. `region` is "1/16" (the
    irreducible triangle) or "1/8" (that triangle plus its mirror image,
    whose points duplicate the first half and serve as a symmetry check).
    """
    if abs(period_a - period_b) > 1e-6:
        raise ValueError("substrate period is not square ({:.3f} x {:.3f} A); "
                         "the wedge logic assumes a square surface lattice"
                         .format(period_a, period_b))
    n = max(2, round(period_a / spacing))
    if n % 2:
        n += 1                                   # need a point at the half-cell
    half = n // 2
    pts = []
    for i in range(half + 1):
        for j in range(i + 1):
            if region == "1/16" and i + j > half:
                continue
            # triangle laid along the y edge: corners (0,0), (0,L/2), (L/2,L/2)
            pts.append((j / n, i / n))
    return pts, period_a / n, n


# --------------------------------------------------------------------------
#  Input construction
# --------------------------------------------------------------------------
def add_dipole(text, zlo, zhi):
    """Sawtooth dipole correction, its drop region centred on the vacuum."""
    vac = 1.0 - (zhi - zlo)
    eopreg = min(EOPREG_MAX, vac / 3.0)
    centre = ((zhi + zlo + 1.0) / 2.0) % 1.0
    emaxpos = (centre - eopreg / 2.0) % 1.0
    # tefield/dipfield live in &CONTROL; the sawtooth's shape lives in &SYSTEM
    for key, val in (("tefield", ".true."), ("dipfield", ".true.")):
        text = qi.set_key(text, "control", key, val)
    for key, val in (("edir", "3"), ("eamp", "0.0"),
                     ("emaxpos", "{:.4f}".format(emaxpos)),
                     ("eopreg", "{:.4f}".format(eopreg))):
        text = qi.set_key(text, "system", key, val)
    return text


def add_spin(text, species, parent, label):
    """Adatom as its own species (same .upf) carrying the starting moment."""
    mass, upf = next((m, u) for lab, m, u in species if lab == parent)
    species = species + [(label, mass, upf)]
    text = set_species(text, species)
    text = qi.set_key(text, "system", "ntyp", str(len(species)))
    text = qi.set_key(text, "system", "nspin", "2")
    return qi.set_key(text, "system",
                      f"starting_magnetization({len(species)})", str(START_MAG))


def build_case(text, base, element, xy, height, spin, dipole, geom):
    """Return (input text, info dict) for one adatom position."""
    a, b, c, zlo, zhi = geom
    label = f"{element}1" if spin else element
    z = (zhi * c + height) / c
    atoms = list(base) + [(label, [xy[0], xy[1], z], [])]

    text = set_atoms(text, atoms)
    text = qi.set_key(text, "system", "nat", str(len(atoms)))
    if spin:
        text = add_spin(text, get_species(text), element, label)
    if dipole:
        text = add_dipole(text, zlo, z)

    nearest = min(math.sqrt((_wrap(fx - xy[0]) * a) ** 2
                            + (_wrap(fy - xy[1]) * b) ** 2
                            + (_wrap(fz - z) * c) ** 2)
                  for _l, (fx, fy, fz), _e in base)
    return text, {"z": z, "nearest": nearest,
                  "vacuum": (1.0 - (zhi - zlo)) * c - height}


# --------------------------------------------------------------------------
#  Prompts
# --------------------------------------------------------------------------
def ask(question, default=None, choices=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        reply = input(f"{question}{suffix}: ").strip()
        if not reply and default is not None:
            reply = str(default)
        if not reply:
            continue
        if choices and reply not in choices:
            print("   choose one of: " + ", ".join(choices))
            continue
        return reply


def main():
    if not os.path.exists("scf.in"):
        sys.exit("make_deposition: no scf.in in this directory")

    text = qi.read_input("scf.in")
    a, b, c = check_cell(qi.get_cell(text))
    unit, atoms = get_atoms(text)
    if unit != "crystal":
        sys.exit(f"make_deposition: ATOMIC_POSITIONS are in '{unit}', need 'crystal'")
    species = get_species(text)
    zhi, layer = top_layer(atoms, c)
    zlo = min(at[1][2] for at in atoms)
    pa, pb = substrate_period(atoms, layer, a, b)

    print("cell            {:.3f} x {:.3f} x {:.3f} A".format(a, b, c))
    print("substrate period {:.3f} x {:.3f} A".format(pa, pb))
    print("top layer at z = {:.3f} A, vacuum {:.3f} A, {} atoms"
          .format(zhi * c, (1.0 - (zhi - zlo)) * c, len(atoms)))

    labels = [lab for lab, _m, _u in species]
    element = ask("adatom element " + "/".join(labels), labels[0], labels)
    spin_mode = ask("spin (none/spin/both)", "none", ["none", "spin", "both"])
    heights = [float(x) for x in ask("heights in A, space separated", "1 2 3").split()]
    region = ask("wedge region (1/16 irreducible, 1/8 with duplicate checks)",
                 "1/16", ["1/16", "1/8"])
    spacing = float(ask("wedge grid spacing in A", "{:.3f}".format(pa / 8)))
    dipole = ask("dipole correction (y/n)", "y", ["y", "n"]) == "y"

    points, step, n = wedge_points(pa, pb, spacing, region)
    print("\n{} points on a {:.3f} A grid ({} divisions of the period)"
          .format(len(points), step, n))

    spins = {"none": [False], "spin": [True], "both": [False, True]}[spin_mode]
    geom = (a, b, c, zlo, zhi)
    made = 0
    print("  {:>7} {:>6} {:>13} {:>8} {:>8}  {}".format(
        "height", "spin", "x,y (A)", "d_min", "site", "path"))
    for spin in spins:
        for height in heights:
            for fx, fy in points:
                # wedge coordinates are fractions of the period, not of the cell
                xy = (fx * pa / a, fy * pb / b)
                case, info = build_case(text, atoms, element, xy, height,
                                        spin, dipole, geom)
                path = os.path.join(element, "spin" if spin else "nospin",
                                    "h" + fmt_height(height),
                                    "xy_{:.3f}_{:.3f}".format(fx * pa, fy * pb))
                if os.path.exists(os.path.join(path, "scf.in")):
                    sys.exit(f"make_deposition: {path}/scf.in already exists")
                os.makedirs(path, exist_ok=True)
                with open(os.path.join(path, "scf.in"), "w") as fh:
                    fh.write(case)
                made += 1
                print("  {:7.2f} {:>6} {:6.3f},{:6.3f} {:8.3f} {:>8}  {}".format(
                    height, "yes" if spin else "no", fx * pa, fy * pb,
                    info["nearest"], site_label(xy, layer, a, b, c), path))
                if info["vacuum"] < VACUUM_WARN_ANG:
                    print("    warning: only {:.1f} A of vacuum above the adatom"
                          .format(info["vacuum"]))
    print("\n{} inputs written".format(made))


if __name__ == "__main__":
    main()
