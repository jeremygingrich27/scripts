"""poscar_lib.py — shared POSCAR helpers for the editor scripts.

Import as `import poscar_lib as pl` (the editor/ directory is on sys.path when a
script there is run directly). numpy is imported lazily so the pure text helpers
work even where numpy is unavailable.
"""
from pathlib import Path


def read_poscar(fname):
    """Return the POSCAR lines, keeping line endings."""
    return Path(fname).read_text().splitlines(keepends=True)


def write_poscar(fname, lines):
    Path(fname).write_text("".join(lines))


def scale_lattice(lines, factors):
    """Scale lattice vectors (lines 3-5) by per-axis factors; returns lines."""
    factors = [float(f) for f in factors]
    for i in range(3):
        vec = [float(x) for x in lines[i + 2].split()]
        lines[i + 2] = "  " + "  ".join(f"{x * factors[i]:.16f}" for x in vec) + "\n"
    return lines


def fmt_tag(factors):
    """Filename-friendly tag, e.g. [1, 1, 0.98] -> '1_1_0.98'."""
    parts = []
    for f in factors:
        s = f"{float(f):.3f}"
        parts.append(s.rstrip("0").rstrip(".") if "." in s else s)
    return "_".join(parts)


def lattice_vectors(fname):
    """Return the 3x3 lattice (Å), including the global scale factor (line 2)."""
    import numpy as np
    lines = Path(fname).read_text().splitlines()
    scale = float(lines[1].split()[0])
    return np.array([[float(x) for x in lines[i].split()[:3]] for i in (2, 3, 4)]) * scale


def lattice_lengths(fname):
    import numpy as np
    return np.linalg.norm(lattice_vectors(fname), axis=1)


def cell_volume(fname):
    import numpy as np
    a, b, c = lattice_vectors(fname)
    return abs(np.dot(a, np.cross(b, c)))


def read_structure(fname):
    """Parse a POSCAR into a dict: comment, cell (3x3 Å), species, counts,
    frac (N x 3 fractional). The global scale factor is folded into `cell`, and
    Cartesian input is converted to fractional, so `frac` is always Direct.
    Selective dynamics flags are dropped (nothing here uses them).
    """
    import numpy as np
    lines = Path(fname).read_text().splitlines()
    scale = float(lines[1].split()[0])
    cell = np.array([[float(x) for x in lines[i].split()[:3]] for i in (2, 3, 4)]) * scale
    species = lines[5].split()
    counts = [int(n) for n in lines[6].split()]
    i = 7
    if lines[i].strip()[:1].upper() == "S":   # selective dynamics
        i += 1
    cartesian = lines[i].strip()[:1].upper() in ("C", "K")
    i += 1
    n = sum(counts)
    pos = np.array([[float(x) for x in lines[i + j].split()[:3]] for j in range(n)])
    if cartesian:
        pos = pos @ np.linalg.inv(cell)
    return {"comment": lines[0], "cell": cell, "species": species,
            "counts": counts, "frac": pos}


def write_structure(fname, st):
    """Write a structure dict (see read_structure) as a Direct POSCAR."""
    out = [st["comment"].rstrip(), "   1.00000000000000"]
    out += ["  " + "  ".join(f"{x:.16f}" for x in v) for v in st["cell"]]
    out += ["   " + "   ".join(st["species"]),
            "   " + "   ".join(str(c) for c in st["counts"]), "Direct"]
    out += ["  " + "  ".join(f"{x:.16f}" for x in p) for p in st["frac"]]
    Path(fname).write_text("\n".join(out) + "\n")
