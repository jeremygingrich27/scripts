"""qe_input.py — shared helpers for editing Quantum ESPRESSO `pw.x` inputs.

The only module that knows QE input syntax; the generator scripts
(gen_ecut, gen_kpoints, gen_scale) are thin CLIs on top of it.

Scope is deliberately narrow: **ibrav = 0 inputs with an explicit
CELL_PARAMETERS block**. Anything else is rejected by `get_cell`, which keeps
the rest of the code free of Bravais-lattice / celldm special cases.
"""

import os
import re


# --------------------------------------------------------------------------
#  Reading / writing
# --------------------------------------------------------------------------
def read_input(path):
    """Return the full text of a pw.x input file."""
    with open(path) as fh:
        return fh.read()


def write_case(parent, name, text):
    """Create parent/name/ and write `text` to scf.in inside it.

    Returns the path to the created directory."""
    case = os.path.join(parent, name)
    os.makedirs(case, exist_ok=True)
    with open(os.path.join(case, "scf.in"), "w") as fh:
        fh.write(text)
    return case


# --------------------------------------------------------------------------
#  Namelist keys  (&CONTROL, &SYSTEM, ...)
# --------------------------------------------------------------------------
def get_key(text, key):
    """Return the raw value of `key = value` from the namelists, or None.

    `key` is matched case-insensitively anywhere in the namelists (keys are
    unique across QE namelists, so the namelist name isn't needed to read)."""
    m = re.search(rf"(?im)^\s*{re.escape(key)}\s*=\s*([^\n!,]+)", text)
    return m.group(1).strip() if m else None


def set_key(text, namelist, key, value):
    """Set `key = value` inside &namelist (e.g. namelist='system'), inserting
    the line just before the namelist's closing '/' if it isn't already there.
    The namelist itself must exist in the template."""
    lines = text.splitlines()
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and re.match(rf"(?i)^\s*&{namelist}\b", ln):
            start = i
        elif start is not None and ln.strip() == "/":
            end = i
            break
    if start is None or end is None:
        raise ValueError(f"namelist &{namelist} not found in input")

    new_line = f"  {key} = {value}"
    for i in range(start + 1, end):
        if re.match(rf"(?i)^\s*{re.escape(key)}\s*=", lines[i]):
            lines[i] = new_line
            return "\n".join(lines) + "\n"
    lines.insert(end, new_line)
    return "\n".join(lines) + "\n"


def _remove_key(text, namelist, key):
    """Remove the `key = ...` line from &namelist if present; no-op otherwise.
    Scoped to the namelist the same way set_key matches, so an unrelated key of
    the same name elsewhere is left alone."""
    lines = text.splitlines()
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and re.match(rf"(?i)^\s*&{namelist}\b", ln):
            start = i
        elif start is not None and ln.strip() == "/":
            end = i
            break
    if start is None or end is None:
        return text
    kept = [ln for i, ln in enumerate(lines)
            if not (start < i < end and re.match(rf"(?i)^\s*{re.escape(key)}\s*=", ln))]
    return "\n".join(kept) + "\n"


def set_occupations(text, mode, smearing="gaussian", degauss=0.004):
    """Set the &SYSTEM occupation scheme.

    mode='fixed'    : insulator/semiconductor occupations. Any leftover
                      `smearing`/`degauss` keys are removed — they are
                      inconsistent with fixed occupations, and (the reason this
                      helper exists) they make ph.x classify the system as a
                      metal and refuse epsil/Born-charge calculations.
    mode='smearing' : metallic occupations with the given `smearing` type and
                      `degauss` (Ry).
    """
    mode = mode.lower()
    if mode not in ("fixed", "smearing"):
        raise ValueError(
            f"occupations mode must be 'fixed' or 'smearing', got {mode!r}")
    text = set_key(text, "system", "occupations", f"'{mode}'")
    if mode == "fixed":
        text = _remove_key(text, "system", "smearing")
        text = _remove_key(text, "system", "degauss")
    else:
        text = set_key(text, "system", "smearing", f"'{smearing}'")
        text = set_key(text, "system", "degauss", f"{degauss}")
    return text


def set_pseudo_dir(text, abspath):
    """Force pseudo_dir to an absolute path so pw.x resolves the .upf files
    even when run from a sweep subdirectory."""
    return set_key(text, "control", "pseudo_dir", f"'{abspath}'")


def set_ecut(text, ecut):
    """Set ecutwfc (Ry) in &SYSTEM."""
    return set_key(text, "system", "ecutwfc", f"{ecut}")


def _ensure_namelist(text, name, after):
    """Make sure an (empty) &name / block exists, inserting it right after the
    closing '/' of namelist `after` if it's missing."""
    if re.search(rf"(?im)^\s*&{name}\b", text):
        return text
    lines = text.splitlines()
    started = False
    for i, ln in enumerate(lines):
        if not started and re.match(rf"(?i)^\s*&{after}\b", ln):
            started = True
        elif started and ln.strip() == "/":
            lines.insert(i + 1, f"&{name.upper()}")
            lines.insert(i + 2, "/")
            return "\n".join(lines) + "\n"
    raise ValueError(f"cannot place &{name}: namelist &{after} not found")


def make_relax(text, calculation="vc-relax", cell_dofree="all", press=None):
    """Convert an SCF input into a relaxation input: set `calculation`, and for
    vc-relax ensure &IONS + &CELL exist with `cell_dofree` (and `press`)."""
    text = set_key(text, "control", "calculation", f"'{calculation}'")
    text = _ensure_namelist(text, "ions", after="electrons")
    if calculation == "vc-relax":
        text = _ensure_namelist(text, "cell", after="ions")
        text = set_key(text, "cell", "cell_dofree", f"'{cell_dofree}'")
        if press is not None:
            text = set_key(text, "cell", "press", f"{press}")
    return text


# --------------------------------------------------------------------------
#  CELL_PARAMETERS  (ibrav = 0 only)
# --------------------------------------------------------------------------
def _find_cell(lines):
    """Return (header_index, unit_string) for the CELL_PARAMETERS card, or
    raise if this isn't an ibrav=0 + explicit-cell input."""
    for i, ln in enumerate(lines):
        m = re.match(r"(?i)^\s*CELL_PARAMETERS\b\s*\(?\s*([a-z]*)", ln)
        if m:
            return i, m.group(1).lower()
    raise ValueError(
        "no CELL_PARAMETERS block found — these scripts require ibrav=0 "
        "with an explicit cell")


def get_cell(text):
    """Return the three lattice vectors as float lists (in the input's own
    units). Raises if there is no explicit CELL_PARAMETERS block."""
    lines = text.splitlines()
    i, _unit = _find_cell(lines)
    return [[float(x) for x in lines[i + 1 + k].split()[:3]] for k in range(3)]


BOHR_TO_ANG = 0.52917721


def get_alat_angstrom(text):
    """alat in angstrom from celldm(1) (bohr) or A (angstrom), or None."""
    celldm = get_key(text, "celldm(1)")
    if celldm is not None:
        return float(celldm.replace("d", "e").replace("D", "e")) * BOHR_TO_ANG
    a = get_key(text, "A")
    return float(a.replace("d", "e").replace("D", "e")) if a is not None else None


def get_cell_angstrom(text):
    """Return the three lattice vectors converted to angstrom, honouring the
    CELL_PARAMETERS unit (angstrom / bohr / alat; no unit means alat if
    celldm(1) or A is set, else bohr — QE's legacy default)."""
    lines = text.splitlines()
    _i, unit = _find_cell(lines)
    alat = get_alat_angstrom(text)
    if unit == "angstrom":
        scale = 1.0
    elif unit == "bohr":
        scale = BOHR_TO_ANG
    elif unit == "alat" or (unit == "" and alat is not None):
        if alat is None:
            raise ValueError("CELL_PARAMETERS in alat but no celldm(1) or A set")
        scale = alat
    else:
        scale = BOHR_TO_ANG
    return [[x * scale for x in v] for v in get_cell(text)]


def set_cell(text, vectors):
    """Rewrite the three CELL_PARAMETERS rows with `vectors`, preserving the
    card's unit header and the rest of the file."""
    lines = text.splitlines()
    i, _unit = _find_cell(lines)
    for k, v in enumerate(vectors):
        lines[i + 1 + k] = "  {:18.12f} {:18.12f} {:18.12f}".format(*v)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
#  ATOMIC_POSITIONS card
# --------------------------------------------------------------------------
def _find_positions(lines):
    """Return (header_index, unit_string) for the ATOMIC_POSITIONS card."""
    for i, ln in enumerate(lines):
        m = re.match(r"(?i)^\s*ATOMIC_POSITIONS\b\s*\(?\s*([a-z]*)", ln)
        if m:
            return i, m.group(1).lower()
    raise ValueError("no ATOMIC_POSITIONS card found")


def get_positions(text):
    """Return (unit, atoms) where atoms is a list of (symbol, [x, y, z]).
    Reads `nat` rows following the ATOMIC_POSITIONS header, skipping blank
    and comment lines (pw.x accepts both inside the card)."""
    lines = text.splitlines()
    nat = int(get_key(text, "nat"))
    i, unit = _find_positions(lines)
    atoms = []
    for ln in lines[i + 1:]:
        if len(atoms) == nat:
            break
        parts = ln.split()
        if not parts or parts[0][0] in "!#":
            continue
        atoms.append((parts[0], [float(parts[1]), float(parts[2]), float(parts[3])]))
    return unit, atoms


def set_positions(text, atoms):
    """Rewrite the ATOMIC_POSITIONS rows with `atoms` (list of
    (symbol, [x, y, z])), preserving the card's unit header."""
    lines = text.splitlines()
    i, _unit = _find_positions(lines)
    for k, (sym, xyz) in enumerate(atoms):
        lines[i + 1 + k] = "  {:3s} {:18.12f} {:18.12f} {:18.12f}".format(sym, *xyz)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
#  K_POINTS card
# --------------------------------------------------------------------------
def set_kpoints(text, mesh):
    """Replace the K_POINTS card with an automatic, unshifted `mesh`
    (a 3-element list)."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        if re.match(r"(?i)^\s*K_POINTS\b", lines[i]):
            out.append("K_POINTS automatic")
            out.append(f"  {mesh[0]} {mesh[1]} {mesh[2]}  0 0 0")
            i += 2  # drop the old card line and its data line
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out) + "\n"
