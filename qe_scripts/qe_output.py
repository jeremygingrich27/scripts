"""qe_output.py — read the relaxed structure out of a pw.x vc-relax output.

Narrow on purpose: it parses the `Begin final coordinates ... End final
coordinates` block that pw.x prints once a (vc-)relax has converged, returning
the cell in angstrom, the atomic positions in crystal (fractional) coordinates,
and the final total energy.
"""

import math
import re

BOHR_TO_ANG = 0.52917721


# --------------------------------------------------------------------------
#  Geometry helpers (shared by the reiteration step)
# --------------------------------------------------------------------------
def vlen(v):
    return math.sqrt(sum(c * c for c in v))


def angle(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (vlen(a) * vlen(b))))))


def lattice_constants(cell):
    """(a, b, c, alpha, beta, gamma) from three lattice vectors."""
    a, b, c = cell
    return (vlen(a), vlen(b), vlen(c),
            angle(b, c), angle(a, c), angle(a, b))


# --------------------------------------------------------------------------
#  Parsing
# --------------------------------------------------------------------------
def _cell_to_ang_scale(unit):
    unit = unit.lower()
    if "bohr" in unit:
        return BOHR_TO_ANG
    if "alat" in unit:
        m = re.search(r"alat\s*=\s*([\d.]+)", unit)
        return float(m.group(1)) * BOHR_TO_ANG if m else 1.0
    return 1.0  # angstrom (or unitless)


def parse_final_structure(out):
    """Return {'cell', 'atoms', 'energy_ry'} from a finished vc-relax output,
    or None if it never reached 'Begin final coordinates'.

    cell  : three lattice vectors in angstrom
    atoms : list of (symbol, [f1, f2, f3]) in crystal (fractional) coordinates
    """
    if "Begin final coordinates" not in out:
        return None
    tail = out.split("Begin final coordinates", 1)[1]
    if "End final coordinates" in tail:
        tail = tail.split("End final coordinates", 1)[0]

    cm = re.search(r"(?i)CELL_PARAMETERS\s*\(([^)]*)\)", tail)
    if not cm:
        return None
    scale = _cell_to_ang_scale(cm.group(1))
    rows = tail[cm.end():].strip().splitlines()[:3]
    cell = [[float(x) * scale for x in r.split()[:3]] for r in rows]

    pm = re.search(r"(?i)ATOMIC_POSITIONS\s*\(([^)]*)\)", tail)
    if not pm:
        return None
    if "crystal" not in pm.group(1).lower():
        raise ValueError("relaxed ATOMIC_POSITIONS are not in crystal units "
                         "(this toolkit assumes crystal coordinates)")
    atoms = []
    for line in tail[pm.end():].strip().splitlines():
        parts = line.split()
        if len(parts) < 4 or not re.match(r"[A-Za-z]", parts[0]):
            break  # past the position rows
        atoms.append((parts[0], [float(parts[1]), float(parts[2]), float(parts[3])]))

    energies = re.findall(r"^!\s+total energy\s+=\s+(-?[\d.]+)\s+Ry", out, re.M)
    return {"cell": cell, "atoms": atoms,
            "energy_ry": float(energies[-1]) if energies else None}
