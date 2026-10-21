#!/usr/bin/env python3
"""
Check the example TARA in _data/tara_bcu.yml and generate an Excel workbook from it.

The workbook keeps the ISO/SAE 21434 logic live: attack potential, feasibility rating,
impact, risk value and CAL are Excel formulas over the "Rating Tables" sheet, so a
reader can change a factor and watch the risk move. The script computes the same
values in Python to enforce the rules listed in the YAML header, and refuses to write
the workbook if any of them fail.

Usage (from the repo root):
    python3 scripts/build_tara.py [_data/tara_bcu.yml] [examples/TARA_BCU_example.xlsx]

Requires: pyyaml, openpyxl (pip install pyyaml openpyxl)
"""
import sys
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]

# --- ISO/SAE 21434 rating tables (Annex G attack potential, Annex H risk matrix,
# --- Annex E CAL example). Values as in the standard's informative examples.
FACTORS = {
    "elapsed_time": [("<=1d", 0), ("<=1w", 1), ("<=1m", 4), ("<=6m", 17), (">6m", 19)],
    "expertise": [("layman", 0), ("proficient", 3), ("expert", 6), ("multiple_experts", 8)],
    "knowledge": [("public", 0), ("restricted", 3), ("confidential", 7), ("strictly_confidential", 11)],
    "window": [("unlimited", 0), ("easy", 1), ("moderate", 4), ("difficult", 10)],
    "equipment": [("standard", 0), ("specialized", 4), ("bespoke", 7), ("multiple_bespoke", 9)],
}
FACTOR_ORDER = list(FACTORS)
FACTOR_TITLES = {"elapsed_time": "Elapsed time", "expertise": "Expertise", "knowledge": "Knowledge of item",
                 "window": "Window of opportunity", "equipment": "Equipment"}
FEASIBILITY = [(13, "High"), (19, "Medium"), (24, "Low"), (10**9, "Very low")]  # upper bounds of attack potential
FEAS_COLS = ["Very low", "Low", "Medium", "High"]
IMPACTS = ["Negligible", "Moderate", "Major", "Severe"]
RISK = {"Severe": [2, 3, 4, 5], "Major": [1, 2, 3, 4], "Moderate": [1, 2, 2, 3], "Negligible": [1, 1, 1, 1]}
VECTORS = ["Physical", "Local", "Adjacent", "Network"]
CAL = {"Severe": [2, 3, 4, 4], "Major": [1, 2, 3, 4], "Moderate": [1, 1, 2, 3], "Negligible": [0, 0, 0, 0]}
STRIDE = ["spoofing", "tampering", "repudiation", "information_disclosure", "denial_of_service",
          "elevation_of_privilege"]
TREATMENTS = ["reduce", "retain", "share", "avoid"]
ACCEPTED_RISK = 2

# --- styles, close to the FMEDA example in examples/
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14)
NOTE = Font(italic=True, color="52514E")
HEAD_FILL = PatternFill("solid", fgColor="E1E0DC")
THIN = Side(style="thin", color="C9C7C1")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top", wrap_text=True)
RISK_FILLS = {1: "D9F2D9", 2: "EAF4C8", 3: "FCE8B2", 4: "F8C9A8", 5: "F2B8B8"}


def label(s):
    return s.replace("_", " ").capitalize()


# ------------------------------------------------------------------ checks ---
def potential(f):
    return sum(dict(FACTORS[k])[f[k]] for k in FACTOR_ORDER)


def feasibility(points):
    return next(name for bound, name in FEASIBILITY if points <= bound)


def risk(impact, feas):
    return RISK[impact][FEAS_COLS.index(feas)]


def check(doc):
    errors = []
    err = errors.append
    assets = {a["id"]: a for a in doc["assets"]}
    dss = {d["id"]: d for d in doc["damage_scenarios"]}
    goals = {g["id"]: g for g in doc["goals"]}
    used_goals = set()
    computed = {}

    for a in doc["assets"]:
        if not set(a["properties"]) <= {"C", "I", "A"}:
            err(f"{a['id']}: unknown property in {a['properties']}")
    for d in doc["damage_scenarios"]:
        if d["asset"] not in assets:
            err(f"{d['id']}: unknown asset {d['asset']}")
        elif d["property"] not in assets[d["asset"]]["properties"]:
            err(f"{d['id']}: property {d['property']} is not listed for {d['asset']}")
        for cat in ("safety", "financial", "operational", "privacy"):
            if d["impact"].get(cat, "").capitalize() not in IMPACTS:
                err(f"{d['id']}: impact {cat} must be one of {IMPACTS}")

    def factors_ok(tid, f, what):
        for k in FACTOR_ORDER:
            if f.get(k) not in dict(FACTORS[k]):
                err(f"{tid}: {what}.{k} = {f.get(k)!r}, expected one of {list(dict(FACTORS[k]))}")
                return False
        return True

    for t in doc["threat_scenarios"]:
        tid = t["id"]
        if t["stride"] not in STRIDE:
            err(f"{tid}: stride {t['stride']!r} unknown")
        if t["vector"].capitalize() not in VECTORS:
            err(f"{tid}: vector {t['vector']!r} unknown")
        if t["treatment"] not in TREATMENTS:
            err(f"{tid}: treatment {t['treatment']!r} unknown")
        missing = [d for d in t["damage"] if d not in dss]
        if missing:
            err(f"{tid}: unknown damage scenario(s) {missing}")
            continue
        if not factors_ok(tid, t["initial"], "initial"):
            continue
        impact = max((ds_impact(dss[d]) for d in t["damage"]), key=IMPACTS.index)
        pot = potential(t["initial"])
        r = risk(impact, feasibility(pot))
        res = None
        if r > ACCEPTED_RISK and t["treatment"] == "retain":
            err(f"{tid}: risk {r} > {ACCEPTED_RISK} cannot be retained")
        if t.get("goal"):
            if t["goal"] not in goals:
                err(f"{tid}: unknown goal {t['goal']}")
            used_goals.add(t["goal"])
        if t["treatment"] == "reduce":
            if not t.get("controls") or not t.get("goal") or not t.get("residual"):
                err(f"{tid}: 'reduce' needs controls, goal and residual")
            elif factors_ok(tid, t["residual"], "residual"):
                r_imp = t.get("residual_impact", impact.lower()).capitalize()
                rpot = potential(t["residual"])
                res = risk(r_imp, feasibility(rpot))
                if res > ACCEPTED_RISK:
                    err(f"{tid}: residual risk {res} > {ACCEPTED_RISK} "
                        f"({r_imp} x {feasibility(rpot)}, attack potential {rpot})")
        computed[tid] = (impact, pot, feasibility(pot), r, res)

    for g in goals:
        if g not in used_goals:
            err(f"{g}: goal is not referenced by any threat scenario")
    return errors, computed


def ds_impact(d):
    return max((v.capitalize() for v in d["impact"].values()), key=IMPACTS.index)


# --------------------------------------------------------------- workbook ---
def sheet_header(ws, title, lines, headers, widths):
    ws["A1"] = title
    ws["A1"].font = TITLE
    for i, line in enumerate(lines, 2):
        ws.cell(row=i, column=1, value=line).font = NOTE
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=5, column=c, value=h)
        cell.font, cell.fill, cell.border, cell.alignment = BOLD, HEAD_FILL, BOX, CENTER
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A6"


def put(ws, row, values, center=()):
    for c, v in enumerate(values, 1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.border = BOX
        cell.alignment = CENTER if c in center else WRAP


def color_risk(ws, col, first, last):
    rng = f"{col}{first}:{col}{last}"
    for value, fill in RISK_FILLS.items():
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[str(value)],
                                                      fill=PatternFill("solid", fgColor=fill)))


def build(doc, out):
    meta = doc["document"]
    wb = Workbook()

    # ---- Rating Tables (referenced by every formula) --------------------------
    rt = wb.active
    rt.title = "Rating Tables"
    rt["A1"], rt["A1"].font = "Rating tables (ISO/SAE 21434, informative examples)", TITLE
    rt["A2"], rt["A2"].font = "Every formula in this workbook looks up these tables. Change a table, and the whole TARA follows.", NOTE
    rt["A4"], rt["A4"].font = "Attack potential (Annex G)", BOLD
    put(rt, 5, ["Key", "Factor", "Level", "Points"])
    for c in range(1, 5):
        rt.cell(row=5, column=c).font, rt.cell(row=5, column=c).fill = BOLD, HEAD_FILL
    r = 6
    for k in FACTOR_ORDER:
        for lvl, pts in FACTORS[k]:
            put(rt, r, [f"{k}|{lvl}", FACTOR_TITLES[k], label(lvl) if lvl[0].isalpha() else lvl, pts], center=(4,))
            r += 1
    fac_rng = f"'Rating Tables'!$A$6:$D${r - 1}"

    r += 1
    rt.cell(row=r, column=1, value="Attack feasibility rating").font = BOLD
    r += 1
    put(rt, r, ["Attack potential", "Feasibility"])
    for c in (1, 2):
        rt.cell(row=r, column=c).font, rt.cell(row=r, column=c).fill = BOLD, HEAD_FILL
    for lo, hi, name in [(0, 13, "High"), (14, 19, "Medium"), (20, 24, "Low"), (25, None, "Very low")]:
        r += 1
        put(rt, r, [f"{lo}–{hi}" if hi else f">= {lo}", name])

    r += 2
    rt.cell(row=r, column=1, value="Risk matrix (Annex H): impact × feasibility -> risk value 1–5").font = BOLD
    r += 1
    put(rt, r, ["Impact"] + FEAS_COLS)
    for c in range(1, 6):
        rt.cell(row=r, column=c).font, rt.cell(row=r, column=c).fill = BOLD, HEAD_FILL
    risk_top = r + 1
    for imp in reversed(IMPACTS):
        r += 1
        put(rt, r, [imp] + RISK[imp], center=(2, 3, 4, 5))
    risk_rng = f"'Rating Tables'!$B${risk_top}:$E${r}"
    risk_rows = f"'Rating Tables'!$A${risk_top}:$A${r}"
    risk_cols = f"'Rating Tables'!$B${risk_top - 1}:$E${risk_top - 1}"
    color_risk(rt, "B", risk_top, r)
    for col in "CDE":
        color_risk(rt, col, risk_top, r)

    r += 2
    rt.cell(row=r, column=1, value="CAL determination (Annex E example): impact × attack vector").font = BOLD
    r += 1
    put(rt, r, ["Impact"] + VECTORS)
    for c in range(1, 6):
        rt.cell(row=r, column=c).font, rt.cell(row=r, column=c).fill = BOLD, HEAD_FILL
    cal_top = r + 1
    for imp in reversed(IMPACTS):
        r += 1
        put(rt, r, [imp] + [v or "–" for v in CAL[imp]], center=(2, 3, 4, 5))
    cal_rng = f"'Rating Tables'!$B${cal_top}:$E${r}"
    cal_rows = f"'Rating Tables'!$A${cal_top}:$A${r}"
    cal_cols = f"'Rating Tables'!$B${cal_top - 1}:$E${cal_top - 1}"
    for col, w in zip("ABCDE", (26, 22, 22, 12, 12)):
        rt.column_dimensions[col].width = w
    imp_list = '{"Negligible","Moderate","Major","Severe"}'

    # ---- Assets ----------------------------------------------------------------
    ws = wb.create_sheet("Assets", 0)
    sheet_header(ws, meta["title"], [f"Item: {meta['item']}", meta["status"]],
                 ["ID", "Asset", "Location in the BCU", "C", "I", "A"], [8, 46, 60, 5, 5, 5])
    for i, a in enumerate(doc["assets"], 6):
        put(ws, i, [a["id"], a["name"], a["location"]] + ["x" if p in a["properties"] else "" for p in "CIA"],
            center=(1, 4, 5, 6))

    # ---- Damage Scenarios --------------------------------------------------------
    ws = wb.create_sheet("Damage Scenarios", 1)
    sheet_header(ws, "Damage scenarios and impact rating",
                 ["Impact per category (safety, financial, operational, privacy); the overall impact is the highest one.",
                  "Change a category rating and every threat scenario and risk value that depends on it updates."],
                 ["ID", "Asset", "Property", "Damage scenario", "Safety", "Financial", "Operational", "Privacy", "Impact"],
                 [8, 8, 9, 56, 12, 12, 12, 12, 12])
    ds_row = {}
    for i, d in enumerate(doc["damage_scenarios"], 6):
        ds_row[d["id"]] = i
        im = d["impact"]
        f = (f"=INDEX({imp_list},MAX(MATCH(E{i},{imp_list},0),MATCH(F{i},{imp_list},0),"
             f"MATCH(G{i},{imp_list},0),MATCH(H{i},{imp_list},0)))")
        put(ws, i, [d["id"], d["asset"], d["property"], d["text"]] +
            [im[c].capitalize() for c in ("safety", "financial", "operational", "privacy")] + [f],
            center=(1, 2, 3, 5, 6, 7, 8, 9))
        ws.cell(row=i, column=9).font = BOLD

    # ---- Threat Scenarios (initial risk) --------------------------------------------
    ws = wb.create_sheet("Threat Scenarios", 2)
    heads = (["ID", "Damage scenario(s)", "STRIDE", "Attack vector", "Threat scenario", "Attack path"] +
             [FACTOR_TITLES[k] for k in FACTOR_ORDER] +
             ["Attack potential", "Feasibility", "Impact", "Risk value", "CAL"])
    sheet_header(ws, "Threat scenarios, attack feasibility and initial risk",
                 ["Attack potential = sum of the five factor points (Annex G). Feasibility, risk and CAL are looked up in 'Rating Tables'.",
                  "Initial risk = before any cybersecurity control of this project. See 'Risk Treatment' for the residual risk."],
                 heads, [7, 11, 16, 10, 40, 44, 11, 13, 15, 13, 14, 10, 11, 11, 8, 7])
    ts_row = {}
    n_ts = len(doc["threat_scenarios"])
    for i, t in enumerate(doc["threat_scenarios"], 6):
        ts_row[t["id"]] = i
        cols = "GHIJK"
        pot = "=" + "+".join(f"VLOOKUP(\"{k}|\"&SUBSTITUTE(LOWER({c}{i}),\" \",\"_\"),{fac_rng},4,FALSE)"
                             for k, c in zip(FACTOR_ORDER, cols))
        feas = f'=IF(L{i}<=13,"High",IF(L{i}<=19,"Medium",IF(L{i}<=24,"Low","Very low")))'
        dsi = ",".join(f"MATCH('Damage Scenarios'!$I${ds_row[d]},{imp_list},0)" for d in t["damage"])
        imp = f"=INDEX({imp_list},MAX({dsi}))"
        rv = f"=INDEX({risk_rng},MATCH(N{i},{risk_rows},0),MATCH(M{i},{risk_cols},0))"
        cal = (f'=IF(N{i}="Negligible","–","CAL"&INDEX({cal_rng},MATCH(N{i},{cal_rows},0),'
               f'MATCH(D{i},{cal_cols},0)))')
        put(ws, i, [t["id"], ", ".join(t["damage"]), label(t["stride"]), t["vector"].capitalize(),
                    t["text"], t["attack_path"]] +
            [t["initial"][k] if not t["initial"][k][0].isalpha() else label(t["initial"][k]) for k in FACTOR_ORDER] +
            [pot, feas, imp, rv, cal], center=tuple(range(7, 17)) + (1, 2, 4))
        ws.cell(row=i, column=15).font = BOLD
    color_risk(ws, "O", 6, 5 + n_ts)

    # ---- Risk Treatment (residual risk) ----------------------------------------------
    ws = wb.create_sheet("Risk Treatment", 3)
    heads = (["ID", "Initial risk", "Treatment", "Cybersecurity controls", "Goal"] +
             [FACTOR_TITLES[k] for k in FACTOR_ORDER] +
             ["Residual attack potential", "Residual feasibility", "Residual impact", "Residual risk", "Note"])
    sheet_header(ws, "Risk treatment and residual risk",
                 [meta["risk_acceptance"],
                  "Residual factors describe the attack with the controls in place. Residual impact differs from the initial one only where a control removes the damage itself."],
                 heads, [7, 9, 10, 58, 8, 11, 13, 15, 13, 14, 11, 11, 11, 9, 44])
    for i, t in enumerate(doc["threat_scenarios"], 6):
        src = ts_row[t["id"]]
        res = t.get("residual") or t["initial"]
        pot = "=" + "+".join(f"VLOOKUP(\"{k}|\"&SUBSTITUTE(LOWER({c}{i}),\" \",\"_\"),{fac_rng},4,FALSE)"
                             for k, c in zip(FACTOR_ORDER, "FGHIJ"))
        feas = f'=IF(K{i}<=13,"High",IF(K{i}<=19,"Medium",IF(K{i}<=24,"Low","Very low")))'
        imp = (t["residual_impact"].capitalize() if t.get("residual_impact")
               else f"='Threat Scenarios'!N{src}")
        rv = f"=INDEX({risk_rng},MATCH(M{i},{risk_rows},0),MATCH(L{i},{risk_cols},0))"
        put(ws, i, [t["id"], f"='Threat Scenarios'!O{src}", label(t["treatment"]), t.get("controls", ""),
                    t.get("goal", "")] +
            [res[k] if not res[k][0].isalpha() else label(res[k]) for k in FACTOR_ORDER] +
            [pot, feas, imp, rv, t.get("residual_note", "")],
            center=(1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14))
        ws.cell(row=i, column=14).font = BOLD
    color_risk(ws, "B", 6, 5 + n_ts)
    color_risk(ws, "N", 6, 5 + n_ts)

    # ---- Cybersecurity Goals ------------------------------------------------------------
    ws = wb.create_sheet("Cybersecurity Goals", 4)
    sheet_header(ws, "Cybersecurity goals",
                 ["A goal's CAL is the highest CAL of the threat scenarios it treats (Annex E example).",
                  "Controls live in the 'Risk Treatment' sheet; the blog series explains each of them door by door."],
                 ["ID", "Cybersecurity goal", "Threat scenarios", "CAL", "Highest initial risk", "Highest residual risk"],
                 [8, 70, 26, 8, 12, 12])
    for i, g in enumerate(doc["goals"], 6):
        ts = [t["id"] for t in doc["threat_scenarios"] if t.get("goal") == g["id"]]
        cal_parts = ",".join(f"IFERROR(VALUE(RIGHT('Threat Scenarios'!P{ts_row[x]},1)),0)" for x in ts)
        cal = f'=IF(MAX({cal_parts})=0,"–","CAL"&MAX({cal_parts}))'
        r_init = "=MAX(" + ",".join(f"'Threat Scenarios'!O{ts_row[x]}" for x in ts) + ")"
        r_res = "=MAX(" + ",".join(f"'Risk Treatment'!N{ts_row[x]}" for x in ts) + ")"
        put(ws, i, [g["id"], g["text"], ", ".join(ts), cal, r_init, r_res], center=(1, 3, 4, 5, 6))
        ws.cell(row=i, column=4).font = BOLD
    color_risk(ws, "E", 6, 5 + len(doc["goals"]))
    color_risk(ws, "F", 6, 5 + len(doc["goals"]))

    # ---- Legend & Assumptions -------------------------------------------------------------
    ws = wb.create_sheet("Legend & Assumptions")
    ws["A1"], ws["A1"].font = "How to use this workbook", TITLE
    rows = [
        ("Purpose", "Worked example of an ISO/SAE 21434 TARA for the BCU of the 'Create the Foundation' and "
                    "'Securing the Foundation' blog series: assets -> damage scenarios -> threat scenarios -> "
                    "attack feasibility -> risk -> treatment -> cybersecurity goals."),
        ("Status of the numbers", meta["status"] + " Impact ratings, attack-potential factors and residual "
                                  "ratings are teaching values chosen to show the method, not results of a real analysis."),
        ("Source of truth", "_data/tara_bcu.yml in the blog repository. This workbook is generated by "
                            "scripts/build_tara.py, which also checks the rules below. Edit the YAML, not the workbook, "
                            "if you want the change to survive."),
        ("Live formulas", "Attack potential, feasibility, impact, risk value, CAL and the goal summary are formulas "
                          "over 'Rating Tables'. Change a factor or an impact rating to see the effect."),
        ("Attack potential", "Annex G of ISO/SAE 21434 (based on ISO/IEC 18045): elapsed time, specialist expertise, "
                             "knowledge of the item, window of opportunity, equipment. Higher points = harder attack."),
        ("Feasibility", "0–13 High, 14–19 Medium, 20–24 Low, >= 25 Very low."),
        ("Risk value", "Risk matrix from Annex H: 1 (lowest) to 5 (highest)."),
        ("Acceptance", meta["risk_acceptance"]),
        ("CAL", "Cybersecurity assurance level from the Annex E example table (impact × attack vector). "
                "It sets the rigor of development and verification, not the strength of a mechanism."),
        ("Attack vector", "Network: remote. Adjacent: short-range radio. Local: OBD port, USB, direct bus access "
                          "through a connector. Physical: the attacker has to manipulate the hardware itself."),
        ("Rules enforced by the script", "Every reference resolves; initial risk >= 3 is never retained; every "
                                         "'reduce' has controls, a goal and a residual rating; residual risk <= 2; "
                                         "every goal treats at least one threat."),
        ("What a real TARA adds", "Item definition and boundary, assumptions about the operational environment, "
                                  "cybersecurity claims for retained/shared risks, traceability to requirements and "
                                  "verification, and a review by people who did not write it."),
    ]
    for i, (k, v) in enumerate(rows, 3):
        ws.cell(row=i, column=1, value=k).font = BOLD
        ws.cell(row=i, column=1).alignment = WRAP
        ws.cell(row=i, column=2, value=v).alignment = WRAP
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_data" / "tara_bcu.yml"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "examples" / "TARA_BCU_example.xlsx"
    doc = yaml.safe_load(src.read_text())
    errors, computed = check(doc)
    if errors:
        print("TARA check failed:", *errors, sep="\n  ")
        sys.exit(1)
    print(f"{'ID':5} {'Impact':10} {'AP':>3} {'Feasibility':11} {'Risk':>4} {'Residual':>8}")
    for tid, (imp, pot, feas, r, res) in computed.items():
        print(f"{tid:5} {imp:10} {pot:3} {feas:11} {r:4} {res if res is not None else '-':>8}")
    build(doc, out)
    print(f"Wrote {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")


if __name__ == "__main__":
    main()
