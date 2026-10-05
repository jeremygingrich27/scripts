#!/usr/bin/env python3
"""Harvest vacuum pair-interaction curves (gen_pair_curve.py trees) into tables.

Implements the pseudocode signed off 2026-10-03. No plotting.

    harvest_pair_curves.py [FUNC_DIR ...] [--tols "10 5 1"]     (default: cwd)

In each FUNC_DIR (e.g. separation_tests/pbe):
  pairs = subdirs holding parallel/ and/or antiparallel/ (Sc-Sc, Sc-N, N-N, N2-N2_*)
  refs  = atom_<El>/scf.out

A case is OK only if its scf.out has "JOB DONE", a final "convergence has been
achieved" and no "convergence NOT achieved"; otherwise FAIL with the reason.
Per separation the lower-energy OK start is chosen, and

    E_bind  = E_chosen - E_A - E_B                 (isolated-atom references)
    E_rel12 = E_chosen - E_chosen(largest d)

Flags: SWITCH (chosen start differs from the previous row), SINGLE (only one
start converged), NONE (neither converged; row kept with N/A).
Interaction range for tolerance t: the smallest d such that every OK row at
d' >= d has |E_rel12(d')| < t. d_min is the lowest grid point plus the vertex of
the parabola through it and its two neighbours.

Writes FUNC_DIR/curve_data/{<pair>.dat, atom_refs.dat, summary.dat}, rebuilt
whole on every run.
"""

import argparse
import re
import sys
from pathlib import Path

RY_TO_EV = 13.605693122994
NA = "N/A"


def read_case(scf_out):
    """dict(ok, reason, E_ry, M_tot, M_abs, iters, wall) for one scf.out."""
    if not scf_out.is_file():
        return {"ok": False, "reason": "no scf.out"}
    text = scf_out.read_text(errors="replace")
    if "convergence NOT achieved" in text:
        return {"ok": False, "reason": "convergence NOT achieved"}
    if "JOB DONE" not in text:
        return {"ok": False, "reason": "no JOB DONE"}
    conv = re.findall(r"convergence has been achieved in\s+(\d+)\s+iterations", text)
    energies = re.findall(r"^!\s+total energy\s+=\s+(-?[\d.]+)\s+Ry", text, re.M)
    if not conv or not energies:
        return {"ok": False, "reason": "no converged energy"}
    m_tot = re.findall(r"total magnetization\s+=\s+(-?[\d.]+)", text)
    m_abs = re.findall(r"absolute magnetization\s+=\s+(-?[\d.]+)", text)
    wall = re.findall(r"PWSCF\s*:.*?CPU\s+(.*?)\s+WALL", text)
    return {"ok": True, "reason": "", "E_ry": float(energies[-1]),
            "M_tot": float(m_tot[-1]) if m_tot else None,
            "M_abs": float(m_abs[-1]) if m_abs else None,
            "iters": int(conv[-1]), "wall": wall[-1].replace(" ", "") if wall else NA}


def pair_elements(name):
    """'Sc-N' -> ['Sc', 'N']; 'N2-N2_parallel' -> ['N', 'N', 'N', 'N']."""
    out = []
    for part in name.split("_")[0].split("-"):
        m = re.fullmatch(r"([A-Z][a-z]?)(\d*)", part)
        out += [m.group(1)] * (int(m.group(2)) if m.group(2) else 1)
    return out


def parabola_vertex(pts):
    """Vertex (x, y) of the parabola through three (x, y) points, or None."""
    (x1, y1), (x2, y2), (x3, y3) = pts
    den = (x1 - x2) * (x1 - x3) * (x2 - x3)
    a = (x3 * (y2 - y1) + x2 * (y1 - y3) + x1 * (y3 - y2)) / den
    b = (x3 ** 2 * (y1 - y2) + x2 ** 2 * (y3 - y1) + x1 ** 2 * (y2 - y3)) / den
    c = (x2 * x3 * (x2 - x3) * y1 + x3 * x1 * (x3 - x1) * y2 + x1 * x2 * (x1 - x2) * y3) / den
    if a <= 0:
        return None
    xv = -b / (2 * a)
    return xv, a * xv ** 2 + b * xv + c


def fmt(v, spec):
    return NA if v is None else format(v, spec)


def harvest(func_dir, tols):
    func_dir = Path(func_dir)
    out_dir = func_dir / "curve_data"
    out_dir.mkdir(exist_ok=True)

    refs = {}
    for d in sorted(func_dir.glob("atom_*")):
        refs[d.name[5:]] = read_case(d / "scf.out")
    with open(out_dir / "atom_refs.dat", "w") as fh:
        fh.write("# element  E_ry  E_eV  M_tot  M_abs  iters  status\n")
        for el, r in refs.items():
            fh.write(f"{el:4s} {fmt(r.get('E_ry'), '.8f')} "
                     f"{fmt(r['E_ry'] * RY_TO_EV if r['ok'] else None, '.6f')} "
                     f"{fmt(r.get('M_tot'), '.2f')} {fmt(r.get('M_abs'), '.2f')} "
                     f"{r.get('iters', NA)} {'OK' if r['ok'] else 'FAIL: ' + r['reason']}\n")

    pairs = sorted(p for p in func_dir.iterdir()
                   if p.is_dir() and ((p / "parallel").is_dir() or (p / "antiparallel").is_dir()))
    summary = []
    for pair in pairs:
        els = pair_elements(pair.name)
        ref_ok = all(el in refs and refs[el]["ok"] for el in els)
        e_ref = sum(refs[el]["E_ry"] for el in els) if ref_ok else None

        seps = {}
        fails = []
        for start in ("parallel", "antiparallel"):
            for case in sorted((pair / start).glob("d_*A")):
                d = float(case.name[2:-1])
                r = read_case(case / "scf.out")
                seps.setdefault(d, {})[start] = r
                if not r["ok"]:
                    fails.append(f"{pair.name}/{start}/{case.name}: {r['reason']}")

        rows, prev = [], None
        for d in sorted(seps):
            par, anti = seps[d].get("parallel"), seps[d].get("antiparallel")
            ok = [(s, r) for s, r in (("P", par), ("A", anti)) if r and r["ok"]]
            chosen = min(ok, key=lambda t: t[1]["E_ry"]) if ok else None
            flags = []
            if not ok:
                flags.append("NONE")
            elif len(ok) == 1:
                flags.append("SINGLE")
            if chosen and prev and chosen[0] != prev:
                flags.append("SWITCH")
            if chosen:
                prev = chosen[0]
            rows.append({"d": d, "par": par, "anti": anti, "chosen": chosen, "flags": flags})

        ok_rows = [r for r in rows if r["chosen"]]
        e_far = ok_rows[-1]["chosen"][1]["E_ry"] if ok_rows else None
        for r in rows:
            e = r["chosen"][1]["E_ry"] if r["chosen"] else None
            r["E_bind"] = (e - e_ref) * RY_TO_EV if (e is not None and e_ref is not None) else None
            r["E_rel"] = (e - e_far) * RY_TO_EV if (e is not None and e_far is not None) else None

        with open(out_dir / f"{pair.name}.dat", "w") as fh:
            fh.write(f"# {pair.name} pair curve, {func_dir.name}. Energies: E in Ry; E_bind, E_rel12 in eV.\n"
                     f"# E_bind = E_chosen - sum(isolated atoms {'+'.join(els)}); "
                     f"E_rel12 = E_chosen - E_chosen(largest d). chosen: P parallel / A antiparallel start.\n"
                     "# d_A  E_par_Ry  M_par  E_anti_Ry  M_anti  chosen  E_chosen_Ry  E_bind_eV  E_rel12_eV  flags\n")
            for r in rows:
                p, a, c = r["par"], r["anti"], r["chosen"]
                fh.write(f"{r['d']:7.3f} "
                         f"{fmt(p['E_ry'] if p and p['ok'] else None, '.8f')} "
                         f"{fmt(p['M_tot'] if p and p['ok'] else None, '.2f')} "
                         f"{fmt(a['E_ry'] if a and a['ok'] else None, '.8f')} "
                         f"{fmt(a['M_tot'] if a and a['ok'] else None, '.2f')} "
                         f"{c[0] if c else NA} {fmt(c[1]['E_ry'] if c else None, '.8f')} "
                         f"{fmt(r['E_bind'], '.6f')} {fmt(r['E_rel'], '.6f')} "
                         f"{','.join(r['flags']) or '-'}\n")

        # d_min: lowest grid point + parabola through it and its neighbours
        dmin = dpar = ebind_min = None
        if ok_rows:
            i = min(range(len(ok_rows)), key=lambda k: ok_rows[k]["chosen"][1]["E_ry"])
            dmin = ok_rows[i]["d"]
            key = "E_bind" if e_ref is not None else "E_rel"
            ebind_min = ok_rows[i][key]
            if 0 < i < len(ok_rows) - 1:
                v = parabola_vertex([(ok_rows[k]["d"], ok_rows[k]["chosen"][1]["E_ry"]) for k in (i - 1, i, i + 1)])
                dpar = v[0] if v else None
        # interaction range per tolerance
        ranges = []
        for t in tols:
            rng = None
            for k in range(len(ok_rows)):
                if all(abs(rr["E_rel"]) * 1000 < t for rr in ok_rows[k:]):
                    rng = ok_rows[k]["d"]
                    break
            ranges.append(rng)
        n = lambda f: sum(1 for r in rows if f in r["flags"])
        summary.append((pair.name, dmin, dpar, ebind_min, ok_rows[-1]["E_bind"] if ok_rows else None,
                        ranges, len(fails), n("SINGLE"), n("SWITCH"), n("NONE"), len(rows)))

    with open(out_dir / "summary.dat", "w") as fh:
        fh.write(f"# {func_dir.name}. d in A, energies in eV (E_bind uses isolated atoms; N/A if refs missing).\n"
                 "# pair  d_min_grid  d_min_parabola  E_bind_at_dmin  E_bind_at_dmax  "
                 + "  ".join(f"range_{t:g}meV" for t in tols)
                 + "  n_fail  n_single  n_switch  n_none  n_rows\n")
        for s in summary:
            fh.write(f"{s[0]:18s} {fmt(s[1], '.3f')} {fmt(s[2], '.4f')} {fmt(s[3], '.6f')} {fmt(s[4], '.6f')} "
                     + " ".join(fmt(x, '.3f') for x in s[5])
                     + f" {s[6]} {s[7]} {s[8]} {s[9]} {s[10]}\n")

    print(f"== {func_dir}  ->  {out_dir}/")
    for el, r in refs.items():
        print(f"  ref {el}: {'OK' if r['ok'] else 'FAIL ' + r['reason']}")
    for s in summary:
        print(f"  {s[0]:18s} d_min {fmt(s[1], '.3f')} (parabola {fmt(s[2], '.4f')}) A, "
              f"E_bind(d_min) {fmt(s[3], '.4f')} eV, E_bind(dmax) {fmt(s[4], '.4f')} eV, ranges "
              + ", ".join(f"{t:g} meV: {fmt(x, '.2f')} A" for t, x in zip(tols, s[5]))
              + f" | fail {s[6]} single {s[7]} switch {s[8]} none {s[9]}")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("func_dirs", nargs="*", default=["."], help="functional tree(s), default cwd")
    p.add_argument("--tols", default="10 5 1", help='range tolerances in meV (default "10 5 1")')
    args = p.parse_args(argv)
    tols = [float(t) for t in args.tols.split()]
    for fd in args.func_dirs:
        if not Path(fd).is_dir():
            sys.exit(f"{fd} is not a directory")
        harvest(fd, tols)


if __name__ == "__main__":
    main()
