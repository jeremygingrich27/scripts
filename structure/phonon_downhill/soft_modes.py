#!/usr/bin/env python3
"""Commensurate phonon modes of the cell, and the lowest unstable multiplet.

Reads FORCE_CONSTANTS (phonopy, DIM 1 1 1, so the cell's own modes) and the
masses in phonopy.yaml, imposes the acoustic sum rule by projecting out the
three rigid translations, and diagonalizes the dynamical matrix at Gamma.

Writes into PHONON_DIR:
  modes.dat       every mode: index, frequency (THz)
  multiplet.npz   the lowest multiplet if it is below THRESHOLD:
                  freqs, eigvecs (mass-weighted, 3N x d), masses
Prints UNSTABLE <d> <freq> or STABLE as its last line.

usage: soft_modes.py PHONON_DIR THRESHOLD_THZ DEGEN_TOL_THZ
"""
import sys
import numpy as np
import yaml

THZ = 15.633302    # sqrt(eV / (A^2 amu)) / 2pi, in THz

d, threshold, degen_tol = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])

# masses, one per atom, from phonopy's own record of the cell
masses = np.array([a["mass"] for a in yaml.safe_load(open(d + "/phonopy.yaml"))["unit_cell"]["points"]])
n = len(masses)

# FORCE_CONSTANTS: header "n n", then for each pair a line "i j" and a 3x3 block
lines = open(d + "/FORCE_CONSTANTS").read().split("\n")
fc = np.zeros((3 * n, 3 * n))
k = 1
for i in range(n):
    for j in range(n):
        fc[3 * i:3 * i + 3, 3 * j:3 * j + 3] = [[float(x) for x in lines[k + 1 + r].split()] for r in range(3)]
        k += 4

# dynamical matrix at Gamma (eV / A^2 / amu), symmetrized
w = np.repeat(1 / np.sqrt(masses), 3)
dyn = fc * np.outer(w, w)
dyn = (dyn + dyn.T) / 2

# acoustic sum rule: project out the three rigid translations
t = np.zeros((3 * n, 3))
for a in range(3):
    t[a::3, a] = np.sqrt(masses)
t /= np.linalg.norm(t, axis=0)
proj = np.eye(3 * n) - t @ t.T
dyn = proj @ dyn @ proj

lam, vec = np.linalg.eigh(dyn)
freq = np.sign(lam) * np.sqrt(abs(lam)) * THZ
np.savetxt(d + "/modes.dat", np.column_stack([np.arange(1, 3 * n + 1), freq]), fmt=["%5d", "%12.6f"],
           header="mode  freq(THz)  (ASR by translation projection; negative = imaginary)")

# lowest multiplet (eigh sorts ascending, so it starts at index 0)
if freq[0] >= threshold:
    print("STABLE lowest %.4f THz" % freq[0])
    sys.exit(0)
members = np.where(abs(freq - freq[0]) < degen_tol)[0]
np.savez(d + "/multiplet.npz", freqs=freq[members], eigvecs=vec[:, members], masses=masses)
print("modes", list(members + 1), "freqs", np.round(freq[members], 4))
print("UNSTABLE %d %.4f" % (len(members), freq[0]))
