"""Small shared helpers for the phonon_downhill scripts.

Only plain numpy: POSCAR read/write, INCAR tags, and a few OUTCAR readers.
"""
import re
import numpy as np


# ---------------------------------------------------------------- POSCAR

def read_poscar(path):
    """Return dict(title, lattice 3x3 rows in A, species [..], counts [..], frac Nx3)."""
    lines = open(path).read().splitlines()
    scale = float(lines[1].split()[0])
    lattice = np.array([[float(x) for x in lines[i].split()[:3]] for i in (2, 3, 4)]) * scale
    species = lines[5].split()
    counts = [int(x) for x in lines[6].split()]
    i = 7
    if lines[i].strip()[0] in "sS":          # Selective dynamics line
        i += 1
    cartesian = lines[i].strip()[0] in "cCkK"
    n = sum(counts)
    pos = np.array([[float(x) for x in lines[i + 1 + k].split()[:3]] for k in range(n)])
    frac = pos @ np.linalg.inv(lattice) if cartesian else pos
    return dict(title=lines[0], lattice=lattice, species=species, counts=counts, frac=frac)


def write_poscar(path, s, title=None):
    """Write a VASP5 POSCAR (Direct) from the dict read_poscar returns."""
    out = [title or s["title"], "1.0"]
    out += ["  %21.16f %21.16f %21.16f" % tuple(v) for v in s["lattice"]]
    out += ["  " + "  ".join(s["species"]), "  " + "  ".join(str(c) for c in s["counts"]), "Direct"]
    out += ["  %20.16f %20.16f %20.16f" % tuple(p) for p in s["frac"]]
    open(path, "w").write("\n".join(out) + "\n")


def symbols(s):
    """One element symbol per atom, in POSCAR order."""
    return [sp for sp, c in zip(s["species"], s["counts"]) for _ in range(c)]


# ---------------------------------------------------------------- INCAR

def read_incar(path):
    """INCAR as an ordered dict {TAG: value string}; comments dropped."""
    tags = {}
    for line in open(path):
        line = line.split("#")[0].split("!")[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            tags[k.strip().upper()] = v.strip()
    return tags


def magmom(path):
    """MAGMOM from an INCAR as a float list (expands N*value)."""
    vals = []
    for w in read_incar(path)["MAGMOM"].split():
        if "*" in w:
            n, v = w.split("*")
            vals += [float(v)] * int(n)
        else:
            vals.append(float(w))
    return vals


def set_incar_tags(src, dst, changes):
    """Copy an INCAR, replacing the tags in `changes` (dict) and appending new ones.

    Lines are kept as they are otherwise, so the file still reads like the template.
    """
    done, out = set(), []
    for line in open(src):
        key = line.split("=", 1)[0].strip().upper() if "=" in line.split("#")[0] else None
        if key in changes:
            while out and out[-1].lstrip().startswith("#"):   # its old comment no longer applies
                out.pop()
            out.append("%-11s = %s\n" % (key, changes[key]))
            done.add(key)
        else:
            out.append(line)
    out += ["%-11s = %s\n" % (k, v) for k, v in changes.items() if k not in done]
    open(dst, "w").writelines(out)


# ---------------------------------------------------------------- OUTCAR

def final_energy(outcar):
    """Last 'free  energy   TOTEN' in eV, or None."""
    e = None
    for line in open(outcar):
        if "free  energy   TOTEN" in line:
            e = float(line.split()[-2])
    return e


def finished(outcar):
    """True if VASP wrote its final timing block (the run ended normally)."""
    try:
        return "General timing" in open(outcar).read()
    except FileNotFoundError:
        return False


def onsite_moments(outcar, n_u_atoms):
    """d moments of the first n_u_atoms (the +U atoms) from the LAST LDAUPRINT block.

    moment = trace(spin 1 occupation matrix) - trace(spin 2 occupation matrix).
    """
    text = open(outcar).read().splitlines()
    trace, atom, spin, row = {}, None, None, 0
    for line in text:
        m = re.match(r"atom =\s+(\d+)\s+type =\s+\d+\s+l =\s+2", line)
        if m:
            atom, spin = int(m.group(1)), None
            continue
        if line.startswith("spin component  1"):
            spin, row = 1, 0
            trace[atom, 1] = 0.0
            continue
        if line.startswith("spin component  2"):
            spin, row = 2, 0
            trace[atom, 2] = 0.0
            continue
        if spin and row < 5 and re.match(r"^\s*-?\d", line) and len(line.split()) == 5:
            trace[atom, spin] += float(line.split()[row])   # diagonal element of row `row`
            row += 1
            if row == 5:
                spin = None
    return np.array([trace[i, 1] - trace[i, 2] for i in range(1, n_u_atoms + 1)])
