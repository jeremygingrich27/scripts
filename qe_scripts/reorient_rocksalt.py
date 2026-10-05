#!/usr/bin/env python3
"""reorient_rocksalt.py — rewrite a rocksalt bulk so a3 is along a chosen
surface normal, ready for a slab cut. Writes ONE bulk pw.x input.

Implements the pseudocode signed off 2026-10-05. Reorients only: no slab, no
vacuum, no running.

    reorient_rocksalt.py --bulk BULK_DIR --face 001|111 --out OUT_DIR/scf.in

Bulk geometry: final cell + crystal positions from BULK_DIR/scf.out (vc-relax),
else BULK_DIR/scf.in (build_slab.read_bulk). Everything else (namelists,
species, U) is copied from BULK_DIR/scf.in.

New cell, in conventional-cube coordinates (cube axes are found from the six
nearest neighbours, so a rotated input is fine):
  001: conventional a x a x a cube, a3 = a[001]        (8 atoms, 2+2 per layer)
  111: a1 = a/2[1-10], a2 = a/2[01-1], a3 = a[111]     (6 atoms, hexagonal
       a_hex = a/sqrt2, alternating pure-cation / pure-anion planes, ABC)
Rotated so a1 is along x and a3 along z.

K-mesh: rescaled to keep the bulk's finest reciprocal spacing,
n_i = ceil(|b_i| / dk) with dk = min_j |b_j(bulk)| / n_j(bulk).

Checks (exit on failure): two species in equal number; 6 opposite-species
neighbours at a/2 in the input and in the output; atom count = 2 x (new volume
/ primitive volume); volume per formula unit unchanged.
"""

import argparse
import math
import os
import re
import sys

try:
    from . import qe_input as qi        # imported as part of the qe_scripts package
    from . import make_deposition as md
    from .build_slab import read_bulk
except ImportError:                     # run directly by path (its dir is on sys.path)
    import qe_input as qi
    import make_deposition as md
    from build_slab import read_bulk

TOL = 1e-4          # fractional-coordinate tolerance
DTOL = 0.02         # neighbour-distance tolerance, A

# new lattice vectors in units of a, in the conventional-cube frame
FACES = {
    "001": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    "111": [[0.5, -0.5, 0], [0, 0.5, -0.5], [1, 1, 1]],
}


# ---- small vector helpers -------------------------------------------------
def dot(u, v):
    return sum(x * y for x, y in zip(u, v))


def cross(u, v):
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]


def norm(v):
    return math.sqrt(dot(v, v))


def unit(v):
    n = norm(v)
    return [x / n for x in v]


def det(m):
    return dot(m[0], cross(m[1], m[2]))


def frac_to_cart(f, cell):
    return [sum(f[i] * cell[i][k] for i in range(3)) for k in range(3)]


def cart_to_frac(r, cell):
    """Solve r = f . cell via the reciprocal vectors (no 2*pi)."""
    v = det(cell)
    rec = [cross(cell[1], cell[2]), cross(cell[2], cell[0]), cross(cell[0], cell[1])]
    return [dot(r, rec[i]) / v for i in range(3)]


def reciprocal_lengths(cell):
    v = abs(det(cell))
    return [2 * math.pi * norm(cross(cell[(i + 1) % 3], cell[(i + 2) % 3])) / v
            for i in range(3)]


# ---- rocksalt geometry ----------------------------------------------------
def neighbours(cart, cell, i, rmax):
    """[(element, vector)] of every image of every atom within rmax of atom i."""
    el0, r0 = cart[i]
    out = []
    for n1 in (-1, 0, 1):
        for n2 in (-1, 0, 1):
            for n3 in (-1, 0, 1):
                t = frac_to_cart([n1, n2, n3], cell)
                for j, (el, r) in enumerate(cart):
                    d = [r[k] + t[k] - r0[k] for k in range(3)]
                    if 1e-6 < norm(d) < rmax:
                        out.append((el, d))
    return out


def check_octahedra(cart, cell, a, what):
    """Every atom has exactly 6 opposite-species neighbours at a/2."""
    for i, (el, _r) in enumerate(cart):
        nb = neighbours(cart, cell, i, a / 2 + DTOL)
        if len(nb) != 6 or any(e == el for e, _d in nb) or \
                any(abs(norm(d) - a / 2) > DTOL for _e, d in nb):
            sys.exit(f"{what}: atom {i} ({el}) is not rocksalt-coordinated "
                     f"(found {len(nb)} neighbours within a/2)")


def cube_axes(cart, cell, a):
    """Three orthogonal unit vectors along the cube edges, right-handed."""
    nb = neighbours(cart, cell, 0, a / 2 + DTOL)
    axes = []
    for _e, d in nb:
        u = unit(d)
        if all(abs(dot(u, w)) < 1e-3 for w in axes):
            axes.append(u)
    if len(axes) != 3:
        sys.exit("could not find three orthogonal neighbour directions")
    if det(axes) < 0:
        axes[2] = [-x for x in axes[2]]
    return axes


# ---- k-mesh ---------------------------------------------------------------
def get_kmesh(text):
    m = re.search(r"(?im)^\s*K_POINTS\s*\(?\s*automatic\s*\)?\s*\n\s*(\d+)\s+(\d+)\s+(\d+)", text)
    if not m:
        sys.exit("bulk K_POINTS is not an automatic mesh")
    return [int(m.group(k)) for k in (1, 2, 3)]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bulk", required=True, help="bulk dir with scf.out (vc-relax) or scf.in")
    p.add_argument("--face", choices=sorted(FACES), required=True, help="surface normal")
    p.add_argument("--out", required=True, help="path of the scf.in to write")
    args = p.parse_args(argv)

    # 1. read the bulk
    cell, atoms, source = read_bulk(args.bulk)
    template = qi.read_input(os.path.join(args.bulk, "scf.in"))
    if not re.search(r"(?i)CELL_PARAMETERS\s*\(?\s*angstrom", template):
        sys.exit("bulk scf.in CELL_PARAMETERS must be in angstrom")
    if not re.search(r"(?i)ATOMIC_POSITIONS\s*\(?\s*crystal", template):
        sys.exit("bulk scf.in ATOMIC_POSITIONS must be in crystal units")

    # 2. is it rocksalt?
    species = sorted({el for el, _f in atoms})
    counts = [sum(1 for el, _f in atoms if el == s) for s in species]
    if len(species) != 2 or counts[0] != counts[1]:
        sys.exit(f"need two species in equal number, got {dict(zip(species, counts))}")
    n_fu = counts[0]
    vol = abs(det(cell))
    a = (4 * vol / n_fu) ** (1 / 3)
    cart = [(el, frac_to_cart(f, cell)) for el, f in atoms]
    check_octahedra(cart, cell, a, "input")

    # 3-4. new lattice vectors, then rotate a1 -> x, a3 -> z
    e = cube_axes(cart, cell, a)
    new = [[a * sum(c[j] * e[j][k] for j in range(3)) for k in range(3)] for c in FACES[args.face]]
    if abs(dot(new[0], new[2])) > 1e-6:
        sys.exit("internal: a1 is not perpendicular to a3")
    x = unit(new[0])
    z = unit(new[2])
    y = cross(z, x)
    rot = [[dot(v, x), dot(v, y), dot(v, z)] for v in new]
    rot = [[0.0 if abs(c) < 1e-10 else c for c in v] for v in rot]

    # 5. fill: every image of every bulk atom whose new fractional coords are in [0,1)
    corners = [[i, j, k] for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    span = [cart_to_frac(frac_to_cart(c, new), cell) for c in corners]
    lo = [math.floor(min(s[k] for s in span)) - 1 for k in range(3)]
    hi = [math.ceil(max(s[k] for s in span)) + 1 for k in range(3)]
    filled = []
    for n1 in range(lo[0], hi[0] + 1):
        for n2 in range(lo[1], hi[1] + 1):
            for n3 in range(lo[2], hi[2] + 1):
                for el, f in atoms:
                    g = cart_to_frac(frac_to_cart([f[0] + n1, f[1] + n2, f[2] + n3], cell), new)
                    g = [0.0 if abs(c - round(c)) < TOL and round(c) in (0, 1) else c for c in g]
                    if all(-TOL < c < 1 - TOL for c in g):
                        g = [c % 1.0 for c in g]
                        if not any(el == el2 and all(abs(c - c2) < TOL for c, c2 in zip(g, g2))
                                   for el2, g2 in filled):
                            filled.append((el, g))
    filled.sort(key=lambda t: (round(t[1][2], 6), t[0], t[1][1], t[1][0]))

    # 6. checks
    v_new = abs(det(rot))
    v_prim = vol / n_fu
    expect = 2 * round(v_new / v_prim)
    if abs(v_new / v_prim - round(v_new / v_prim)) > 1e-6:
        sys.exit("internal: new cell is not a whole number of primitive cells")
    if len(filled) != expect:
        sys.exit(f"filled {len(filled)} atoms, expected {expect}")
    if abs(v_new / (len(filled) / 2) - v_prim) > 1e-6:
        sys.exit("volume per formula unit changed")
    check_octahedra([(el, frac_to_cart(g, rot)) for el, g in filled], rot, a, "output")

    # k-mesh: keep the bulk's finest reciprocal spacing
    k_old = get_kmesh(template)
    dk = min(b / n for b, n in zip(reciprocal_lengths(cell), k_old))
    k_new = [max(1, math.ceil(b / dk - 1e-6)) for b in reciprocal_lengths(rot)]

    # 7. write
    text = qi.set_key(template, "system", "nat", str(len(filled)))
    text = md.set_atoms(text, [(el, g, []) for el, g in filled])
    text = qi.set_cell(text, rot)
    text = qi.set_kpoints(text, k_new)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(text)

    lengths = [norm(v) for v in rot]
    gamma = math.degrees(math.acos(dot(rot[0], rot[1]) / (lengths[0] * lengths[1])))
    print(f"{args.out}: rocksalt ({species[0]}{species[1]}) reoriented, a3 || [{args.face}], "
          f"{len(filled)} atoms")
    print(f"  bulk from {source}: a = {a:.5f} A, nn = {a / 2:.5f} A")
    print(f"  cell |a1| = {lengths[0]:.5f}, |a2| = {lengths[1]:.5f}, |a3| = {lengths[2]:.5f} A, "
          f"gamma = {gamma:.1f} deg")
    print(f"  k-mesh {' '.join(map(str, k_old))} -> {' '.join(map(str, k_new))} "
          f"(dk = {dk:.4f} 1/A)")
    zs = sorted({round(g[2] * lengths[2], 5) for _el, g in filled})
    for z in zs:
        here = [el for el, g in filled if abs(g[2] * lengths[2] - z) < 1e-4]
        print(f"  layer z = {z:8.4f} A: " + " ".join(f"{s}x{here.count(s)}" for s in species))
    if len(zs) > 1:
        print(f"  interlayer spacing {zs[1] - zs[0]:.5f} A")


if __name__ == "__main__":
    main()
