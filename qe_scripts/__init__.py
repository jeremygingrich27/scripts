"""qe_scripts — Quantum ESPRESSO convergence/phonon toolkit.

Importable as a package (``from qe_scripts.qe_output import parse_final_structure``)
while every module also stays runnable directly by path (``python3 qe_scripts/
pick_converged.py ...``), which is how the TACC jobscripts invoke them. The
dual-use ``try: from . import ...  except ImportError: import ...`` idiom in the
script modules supports both.
"""
