#!/usr/bin/env python3
import os
import sys
import argparse
import csv
import re
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MultipleLocator

BASE = './'  # adjust if you want to hardcode a different base path
TARGET = 1.92

try:
    import yaml  # optional
except Exception:
    yaml = None

try:
    import openpyxl  # optional
except Exception:
    openpyxl = None


ALLOWED_OPS = ("FT0", "FM0", "FS0")


def parse_binning_string(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            out.append(float(p))
        except Exception:
            return None
    return out or None


def parse_config_binning(path, region_name="TwoLep_SR_HP_mVV"):
    if not path or not os.path.exists(path):
        return None
    in_region = False
    with open(path, "r") as handle:
        for line in handle:
            s = line.strip()
            if s.startswith("Region:"):
                in_region = region_name in s
                continue
            if in_region and s.startswith("Binning:"):
                raw = s.split("Binning:", 1)[1].strip()
                return parse_binning_string(raw)
    return None


def _clean_op_piece(piece):
    s = str(piece).strip()
    # remove common wrappers/punctuation from list-like CLI inputs
    s = s.strip("[](){}")
    s = s.strip().strip(",")
    s = s.strip().strip("\"").strip("'")
    s = s.strip().strip(",")
    return s


def normalize_ops(raw_tokens):
    """Normalize operator CLI inputs into a list like ["FT0","FS0","FM0"].

    Accepts:
      - ["FT0"]
      - ["FT0","FS0","FM0"]
      - ["[FT0,FS0,FM0]"]
      - ["[\"FT0\",\"FS0\",\"FM0\"]"]
      - ["FT0,FS0,FM0"]
    """
    if raw_tokens is None:
        return []
    if isinstance(raw_tokens, str):
        raw_tokens = [raw_tokens]

    ops = []
    for tok in raw_tokens:
        if tok is None:
            continue
        t = str(tok).strip()
        if not t:
            continue

        # If the user passed a JSON-ish / list-ish token, split it.
        if "," in t or "[" in t or "]" in t:
            # Split on commas, but first remove brackets.
            inner = t.strip()
            inner = inner.strip("[]")
            parts = inner.split(",")
            for p in parts:
                c = _clean_op_piece(p)
                if c:
                    ops.append(c)
        else:
            ops.append(_clean_op_piece(t))

    # Handle accidental whitespace-separated without commas, but with quotes/brackets
    ops = [o for o in ops if o]
    ops = [re.sub(r"\s+", "", o) for o in ops]

    bad = [o for o in ops if o not in ALLOWED_OPS]
    if bad:
        raise ValueError(
            "Invalid operator(s): "
            + ", ".join(bad)
            + f". Allowed: {', '.join(ALLOWED_OPS)}"
        )
    return ops


def read_points_yaml(path):
    """
    Preferred reader: uses PyYAML if available, otherwise falls back to a simple parser.
    Returns list of (x, y) sorted by x.
    """
    if yaml is not None:
        data = yaml.safe_load(open(path, "r"))
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Unexpected YAML format or empty file: {path}")
        pts = [(float(row["X"]), float(row["minusdeltaNLL"])) for row in data]
        pts.sort(key=lambda t: t[0])
        return pts

    # Fallback: simple line parser (handles both 'X:' and '- X:')
    pts = []
    x = None
    y = None
    with open(path, "r") as f:
        for line in f:
            s = line.strip()

            # handle "- X: ..." or "X: ..."
            if s.startswith("- "):
                s2 = s[2:].strip()
            else:
                s2 = s

            if s2.startswith("X:"):
                x = float(s2.split("X:", 1)[1].strip())
            elif s2.startswith("minusdeltaNLL:"):
                y = float(s2.split("minusdeltaNLL:", 1)[1].strip())

            if x is not None and y is not None:
                pts.append((x, y))
                x = None
                y = None

    if not pts:
        raise RuntimeError(
            f"No points found in {path}. If you want PyYAML parsing, install it with:\n"
            f"  python3 -m pip install --user pyyaml"
        )
    pts.sort(key=lambda t: t[0])
    return pts


def read_yields_table(path):
    """Read TRExFitter yield table YAML (Table_prefit.yaml).

    Expected structure (list of regions):
      - Region: <name>
        Samples:
          - Sample: <name>
            Yield: <float>
            Error: <float>

    Returns:
      dict[str region][str sample] -> float yield
    """
    if yaml is not None:
        data = yaml.safe_load(open(path, "r"))
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"Unexpected YAML format or empty file: {path}")
        out = {}
        for entry in data:
            region = entry.get("Region")
            if region is None:
                continue
            samples = entry.get("Samples") or []
            regmap = {}
            for s in samples:
                name = s.get("Sample")
                if name is None:
                    continue
                try:
                    regmap[str(name)] = float(s.get("Yield", 0.0))
                except Exception:
                    continue
            out[str(region)] = regmap
        if not out:
            raise RuntimeError(f"No regions/samples found in yield table: {path}")
        return out

    # Fallback: minimal line parser for the structure above.
    out = {}
    region = None
    current_sample = None
    current_yield = None
    with open(path, "r") as f:
        for line in f:
            s = line.strip()
            if s.startswith("- Region:"):
                region = s.split(":", 1)[1].strip()
                out.setdefault(region, {})
                current_sample = None
                current_yield = None
                continue

            if s.startswith("- Sample:"):
                current_sample = s.split(":", 1)[1].strip()
                current_yield = None
                continue

            if s.startswith("Yield:") and region is not None and current_sample is not None:
                try:
                    current_yield = float(s.split(":", 1)[1].strip())
                except Exception:
                    current_yield = None
                if current_yield is not None:
                    out.setdefault(region, {})[current_sample] = current_yield

    if not out:
        raise RuntimeError(
            f"Could not parse yields from {path}. If you want PyYAML parsing, install it with:\n"
            f"  python3 -m pip install --user pyyaml"
        )
    return out


def pick_region_name(all_regions, kind):
    """Pick a region name from the YAML list for a desired kind.

    kind in {"SR_HP", "SR_LP", "CR"}
    """
    regions = list(all_regions)
    if kind == "SR_HP":
        for cand in ("mVV_SR_HP", "SR_HP"):
            for r in regions:
                if cand in r:
                    return r
        for r in regions:
            if "SR_HP" in r:
                return r
        return None
    if kind == "SR_LP":
        for cand in ("mVV_SR_LP", "SR_LP"):
            for r in regions:
                if cand in r:
                    return r
        for r in regions:
            if "SR_LP" in r:
                return r
        return None
    if kind == "CR":
        for cand in ("CR", "ZCR"):
            for r in regions:
                if r == cand:
                    return r
        for r in regions:
            up = r.upper()
            if "CR" in up and "SR_" not in up:
                return r
        return None
    return None


def format_number(x):
    if x is None:
        return ""
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)


def build_yields_rows(op, yields_by_region):
    """Build ordered rows (sample_label, SR_HP, SR_LP, CR)."""
    sr_hp = pick_region_name(yields_by_region.keys(), "SR_HP")
    sr_lp = pick_region_name(yields_by_region.keys(), "SR_LP")
    cr = pick_region_name(yields_by_region.keys(), "CR")

    cols = [("SR_HP", sr_hp), ("SR_LP", sr_lp), ("CR", cr)]

    samples = set()
    for _, rname in cols:
        if rname is None:
            continue
        samples |= set((yields_by_region.get(rname) or {}).keys())

    def y(sample, rname):
        if rname is None:
            return None
        return (yields_by_region.get(rname) or {}).get(sample)

    aqgc_name = f"{op} QUAD"
    order = [
        aqgc_name,
        "EWK VVjj",
        "Z+jets",
        "W+jets",
        "Top",
        "QCD-VV",
        "Total",
    ]

    label_map = {
        aqgc_name: f"aQGC_{op} QUAD",
        "EWK VVjj": "Signal (EWK-VVjj)",
    }

    rows = []
    for s in order:
        if s not in samples:
            continue
        rows.append(
            (
                label_map.get(s, s),
                y(s, sr_hp),
                y(s, sr_lp),
                y(s, cr),
            )
        )

    # Add any remaining samples (stable order)
    for s in sorted(samples):
        if s in order:
            continue
        rows.append((s, y(s, sr_hp), y(s, sr_lp), y(s, cr)))

    return rows, cols


def get_aqgc_quad_yields_row(op, yields_by_region):
    """Return a single row for the aQGC QUAD sample for this operator.

    Row format: (label, SR_HP, SR_LP, CR)
    """
    sr_hp = pick_region_name(yields_by_region.keys(), "SR_HP")
    sr_lp = pick_region_name(yields_by_region.keys(), "SR_LP")
    cr = pick_region_name(yields_by_region.keys(), "CR")

    aqgc_name = f"{op} QUAD"

    def y(region_name):
        if region_name is None:
            return None
        return (yields_by_region.get(region_name) or {}).get(aqgc_name)

    return (
        f"aQGC_{op} QUAD",
        y(sr_hp),
        y(sr_lp),
        y(cr),
    ), [("SR_HP", sr_hp), ("SR_LP", sr_lp), ("CR", cr)]


def get_region_map(yields_by_region):
    sr_hp = pick_region_name(yields_by_region.keys(), "SR_HP")
    sr_lp = pick_region_name(yields_by_region.keys(), "SR_LP")
    cr = pick_region_name(yields_by_region.keys(), "CR")
    return {"SR_HP": sr_hp, "SR_LP": sr_lp, "CR": cr}


def get_sample_yields_row(label, sample_name_in_yaml, yields_by_region, region_map):
    def y(rkey):
        rname = region_map.get(rkey)
        if rname is None:
            return None
        return (yields_by_region.get(rname) or {}).get(sample_name_in_yaml)

    return (label, y("SR_HP"), y("SR_LP"), y("CR"))


def render_text_table(rows, headers):
    table = []
    # compute widths
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(format_number(cell) if i else str(cell)))

    def fmt_row(r):
        parts = []
        for i, cell in enumerate(r):
            txt = str(cell) if i == 0 else format_number(cell)
            if i == 0:
                parts.append(txt.ljust(widths[i]))
            else:
                parts.append(txt.rjust(widths[i]))
        return " | ".join(parts)

    table.append(fmt_row(headers))
    table.append("-+-".join("-" * w for w in widths))
    for r in rows:
        table.append(fmt_row(r))
    return "\n".join(table)


def write_yields_csv(path, op, spe, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["operator", "selection", "sample", "SR_HP", "SR_LP", "CR"])
        for sample, sr_hp, sr_lp, cr in rows:
            w.writerow([op, spe or "", sample, sr_hp, sr_lp, cr])


def write_yields_xlsx(path, op, spe, rows):
    if openpyxl is None:
        return False
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "yields"
    ws.append(["operator", "selection", "sample", "SR_HP", "SR_LP", "CR"])
    for sample, sr_hp, sr_lp, cr in rows:
        ws.append([op, spe or "", sample, sr_hp, sr_lp, cr])
    wb.save(path)
    return True


def find_min_point(pts):
    return min(pts, key=lambda t: t[1])  # (x_min, y_min)


def interpolate_x_at_target(p1, p2, target):
    (x1, y1) = p1
    (x2, y2) = p2
    if y2 == y1:
        return x1
    return x1 + (target - y1) * (x2 - x1) / (y2 - y1)


def find_crossing_one_side(points_in_order, target):
    for p1, p2 in zip(points_in_order, points_in_order[1:]):
        y1 = p1[1]
        y2 = p2[1]

        if (y1 - target) == 0.0:
            return (p1[0], p1, p1)
        if (y2 - target) == 0.0:
            return (p2[0], p2, p2)

        if (y1 - target) * (y2 - target) < 0:
            xcross = interpolate_x_at_target(p1, p2, target)
            return (xcross, p1, p2)

    closest = min(points_in_order, key=lambda p: abs(p[1] - target))
    return (None, closest, None)


def plot_nll_with_cl(output_dir, op, pts, left_cl, right_cl, binning=None,args=None):
    if not pts:
        return None
    os.makedirs(output_dir, exist_ok=True)

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs, ys, marker="o", linestyle="-", color="black", markersize=3)
    ax.axhline(TARGET, color="red", linestyle="--", linewidth=1, label="95% CL")

    if args.x_line_CL:
        if left_cl is not None:
            ax.axvline(left_cl, color="blue", linestyle="--", linewidth=1)
        if right_cl is not None:
            ax.axvline(right_cl, color="blue", linestyle="--", linewidth=1)

    if binning:
        ax.set_xticks(binning)

    ax.set_xlabel(f"{op}")
    ax.set_ylabel("expected -2Δln(L)")
    title = f"CL95 scan: {op}"
    if binning:
        bin_text = ",".join(str(int(b)) if float(b).is_integer() else str(b) for b in binning)
        title = f"{title} \n (binning mVV: {bin_text} GeV)"
    ax.set_title(title)
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(0, 3)

    ax.xaxis.set_major_locator(MultipleLocator(args.x_ticks))
    ax.xaxis.set_minor_locator(AutoMinorLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.yaxis.set_minor_locator(AutoMinorLocator(5))
    ax.tick_params(which="both", direction="in", top=True, right=True)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()

    outpath = os.path.join(output_dir, f"CL95_{op}_curve.png")
    fig.savefig(outpath)
    plt.close(fig)
    return outpath


def main():
    parser = argparse.ArgumentParser(description="Compute 95% CL limits for aQGC operators")
    parser.add_argument(
        "--folder",
        help=(
            "Folder name (relative to cwd) that contains LHoodPlots/ and Tables/. "
            "Example: VBS_SemiLep_aQGC_FT0"
        ),
    )
    parser.add_argument(
        "--op",
        nargs="+",
        help=(
            "Operator(s) to process. Examples: --op FT0 ; --op FT0 FS0 FM0 ; "
            "--op [FT0,FS0,FM0] ; --op [\"FT0\",\"FS0\",\"FM0\"]"
        ),
    )
    parser.add_argument(
        "--ops",
        nargs="+",
        help="Alias for --op (e.g. --ops FT0 FS0 FM0)",
    )
    parser.add_argument(
        "--config",
        help="Config file to read mVV_SR_HP binning from (e.g. VBS_2lep_EFT_Ntuples_FT0.config)",
    )
    parser.add_argument(
        "--binning",
        help="Comma-separated binning for mVV_SR_HP (overrides config), e.g. 0,500,1000,1500,2000,2500,3000,8000",
    )
    parser.add_argument("--Spe", default="")
    parser.add_argument("--out_dir", default="CL_95", help="Output directory for results (default: CL_95)")
    parser.add_argument("--x_ticks", default=0.1, type=float, help="Spacing for x-axis ticks in the NLL plot (default: 0.1)")
    parser.add_argument("--x_line_CL", default=False, type=bool, help="Whether to show a vertical line at the 95% CL level")
    args = parser.parse_args()

    # Folder-mode: derive operator from folder name and use cwd as base.
    folder = args.folder

    raw = args.ops if args.ops else args.op
    if not raw and folder:
        m = re.search(r"(FT0|FM0|FS0)", folder)
        if m:
            raw = [m.group(1)]

    if not raw:
        print("You must provide --op/--ops or --folder with an operator in its name")
        sys.exit(1)

    try:
        ops = normalize_ops(raw)
    except Exception as e:
        print(str(e))
        sys.exit(2)
    spe = args.Spe

    binning = parse_binning_string(args.binning)
    if binning is None:
        config_path = args.config
        if config_path is None and raw:
            candidate = f"VBS_2lep_EFT_Ntuples_{raw[0]}.config"
            if os.path.exists(candidate):
                config_path = candidate
        if config_path:
            binning = parse_config_binning(config_path)

    combined_mode = (len(ops) > 1)

    if spe != "":
        print("Specific selection")
        os.makedirs(f"{args.out_dir}/{spe}", exist_ok=True)
        out_dir = f"{args.out_dir}/{spe}"
    else:
        os.makedirs(args.out_dir, exist_ok=True)
        out_dir = args.out_dir

    if combined_mode:
        outpath = os.path.join(out_dir, "CL95_all.txt")
    else:
        outpath = os.path.join(out_dir, f"CL95_{ops[0]}.txt")
    simple_limits_path = os.path.join(out_dir, "CL95_limits.txt")

    limits_lines = []
    simple_limits_lines = []
    yields_table_rows = []
    yields_sources = {}
    regions_used_by_op = {}

    curve_paths = {}

    yields_by_region_by_op = {}

    for op in ops:
        if folder:
            inpath_base = os.path.join(BASE, folder)
            yield_base = inpath_base
        elif spe != "":
            inpath_base = f"{BASE}/VBS_SemiLep_2L_aQGC_{op}_{spe}/"
            yield_base = f"{BASE}/Yields_VBS_SemiLep_2L_aQGC_{op}_{spe}/"
        else:
            inpath_base = f"{BASE}/VBS_SemiLep_2L_aQGC_{op}/"
            yield_base = f"{BASE}/Yields_VBS_SemiLep_2L_aQGC_{op}/"

        inpath = f"{inpath_base}/LHoodPlots/NLLscan_{op}.yaml"
        if not os.path.exists(inpath):
            print(f"Input not found:\n  {inpath}")
            sys.exit(1)

        pts = read_points_yaml(inpath)
        x_min, y_min = find_min_point(pts)

        left = [p for p in pts if p[0] <= x_min]
        right = [p for p in pts if p[0] >= x_min]
        left_search = list(reversed(left))
        right_search = right

        left_res = find_crossing_one_side(left_search, TARGET)
        right_res = find_crossing_one_side(right_search, TARGET)

        left_CL = round(left_res[0], 3) if left_res[0] is not None else "None"
        right_CL = round(right_res[0], 3) if right_res[0] is not None else "None"
        limits_lines.append(f"{op}: [{left_CL}, {right_CL}]  ")
        simple_limits_lines.append(f"{op}:[{left_CL},{right_CL}]")

        plot_left = left_res[0] if left_res[0] is not None else None
        plot_right = right_res[0] if right_res[0] is not None else None
        plot_path = plot_nll_with_cl(out_dir, op, pts, plot_left, plot_right, binning=binning,args=args)
        if plot_path:
            curve_paths[op] = plot_path

        yield_path = f"{yield_base}/Tables/Table_prefit.yaml"
        yield_path_alt = None
        if "/Yields_" in yield_path:
            yield_path_alt = yield_path.replace("/Yields_", "/Yield_", 1)

        chosen_yield_path = None
        for cand in [yield_path, yield_path_alt]:
            if cand and os.path.exists(cand):
                chosen_yield_path = cand
                break

        if chosen_yield_path is None:
            print(f"WARNING: yield table not found for {op} (skipping yields): {yield_path}")
            if yield_path_alt:
                print(f"  also tried: {yield_path_alt}")
            yields_table_rows.append((f"aQGC_{op} QUAD", None, None, None))
            continue

        try:
            yields_by_region = read_yields_table(chosen_yield_path)
            yields_by_region_by_op[op] = yields_by_region

            row, cols = get_aqgc_quad_yields_row(op, yields_by_region)
            yields_table_rows.append(row)
            yields_sources[op] = chosen_yield_path
            regions_used_by_op[op] = {k: (v or "") for k, v in cols}
        except Exception as e:
            print(f"WARNING: failed to read yields for {op} from {chosen_yield_path}: {e}")
            yields_table_rows.append((f"aQGC_{op} QUAD", None, None, None))

    # Add shared process rows once (from the first operator that had a readable yields table)
    reference_op = None
    for op in ops:
        if op in yields_by_region_by_op:
            reference_op = op
            break

    if reference_op is not None:
        ref_yields = yields_by_region_by_op[reference_op]
        ref_regions = get_region_map(ref_yields)
        common_samples = [
            ("EWK-VVjj", "EWK VVjj"),
            ("Zjets", "Z+jets"),
            ("Wjets", "W+jets"),
            ("Top", "Top"),
            ("QCDVV", "QCD-VV"),
            ("Total", "Total"),
        ]
        for label, sample_name in common_samples:
            yields_table_rows.append(
                get_sample_yields_row(label, sample_name, ref_yields, ref_regions)
            )

    yields_text = render_text_table(yields_table_rows, ["Samples", "SR_HP", "SR_LP", "CR"])

    if combined_mode:
        yields_csv_path = os.path.join(out_dir, "CL95_all_yields_prefit.csv")
        yields_xlsx_path = os.path.join(out_dir, "CL95_all_yields_prefit.xlsx")
        write_yields_csv(yields_csv_path, "ALL", spe, yields_table_rows)
        wrote_xlsx = write_yields_xlsx(yields_xlsx_path, "ALL", spe, yields_table_rows)
    else:
        yields_csv_path = os.path.join(out_dir, f"CL95_{ops[0]}_yields_prefit.csv")
        yields_xlsx_path = os.path.join(out_dir, f"CL95_{ops[0]}_yields_prefit.xlsx")
        write_yields_csv(yields_csv_path, ops[0], spe, yields_table_rows)
        wrote_xlsx = write_yields_xlsx(yields_xlsx_path, ops[0], spe, yields_table_rows)
    if not wrote_xlsx:
        yields_xlsx_path = None

    with open(outpath, "w") as out:
        out.write(f"selection: {spe or ''}\n")
        out.write("operators: " + " ".join(ops) + "\n")
        out.write(f"target_minusdeltaNLL: {TARGET}\n")
        if binning:
            out.write("mVV_SR_HP_binning: " + ",".join(str(int(b)) if float(b).is_integer() else str(b) for b in binning) + "\n")
        out.write("\n")
        out.write("CL95:\n")
        for line in limits_lines:
            out.write(line + "\n")
        out.write("\n")
        if curve_paths:
            out.write("nll_curve_plots:\n")
            for op in ops:
                if op in curve_paths:
                    out.write(f"  {op}: {curve_paths[op]}\n")
            out.write("\n")
        out.write("yields_prefit_sources:\n")
        for op in ops:
            if op in yields_sources:
                out.write(f"  {op}: {yields_sources[op]}\n")
        out.write("\n")
        if regions_used_by_op:
            out.write("regions_used (per op):\n")
            for op in ops:
                if op not in regions_used_by_op:
                    continue
                used = regions_used_by_op[op]
                out.write(
                    f"  {op}: SR_HP={used.get('SR_HP','')} SR_LP={used.get('SR_LP','')} CR={used.get('CR','')}\n"
                )
            out.write("\n")
        out.write("aQGC yields table (prefit):\n")
        out.write(yields_text)
        out.write("\n")

    with open(simple_limits_path, "w") as out_simple:
        for line in simple_limits_lines:
            out_simple.write(line + "\n")

    print(f"Wrote: {outpath}")
    print(f"Wrote: {simple_limits_path}")
    print(f"Wrote: {yields_csv_path}")
    if yields_xlsx_path is not None:
        print(f"Wrote: {yields_xlsx_path}")
    
    print(f"\nCL95 limits for {ops}")
    for op in ops:
        print(f"  {op}: [{left_CL}, {right_CL}]")



if __name__ == "__main__":
    main()