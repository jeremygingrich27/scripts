#!/usr/bin/env python3
"""Build the two INCARs the tree uses from the phase's phonopy disp-run INCAR.

  INCAR.sp     single points (phonon displacements, scan points): the disp INCAR
               with LCHARG = .TRUE. (CHGCARs are moved to $SCRATCH by the jobs)
  INCAR.relax  INCAR.sp + the relax tags below

Everything else (ENCUT 700, PREC Accurate, EDIFF 1E-8, U = 7, AFII MAGMOM,
ISMEAR 0 / SIGMA 0.05, mixing, ISYM 0, ISTART 0 / ICHARG 2) is inherited unchanged.

usage: make_incars.py DISP_INCAR OUTDIR
"""
import sys
from dh_lib import set_incar_tags

src, out = sys.argv[1], sys.argv[2]

SP = {"SYSTEM": "phonon_downhill single point", "LCHARG": ".TRUE."}

RELAX = dict(SP)
RELAX.update({
    "SYSTEM": "phonon_downhill relax",
    "IBRION": "1",                  # (J) quasi-Newton
    "ISIF": "3",                    # (J) cell + ions ...
    "LATTICE_CONSTRAINTS": ".FALSE. .FALSE. .TRUE.",   # (J) ... with a, b fixed (VASP >= 6.4.3)
    "ISYM": "2",                    # (J) symmetrise to the group found in the cell
    "EDIFFG": "-5E-4",              # (J) eV/A force criterion
    "NSW": "60",                    # (J) ionic steps per round
})

set_incar_tags(src, out + "/INCAR.sp", SP)
set_incar_tags(src, out + "/INCAR.relax", RELAX)
