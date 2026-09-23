"""
The six questions.

Each one had a prediction written into docs/log.md before it was run. Where the
prediction was wrong is the interesting part, and those are the paragraphs that
ended up in docs/findings.md.

Every figure here is APPROVED contract value - a ceiling the Board authorised,
not money the state spent.
"""

import argparse
import csv
import os
from collections import defaultdict
from statistics import median

FINAL = "data/final"


def read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def write(name, rows, cols=None):
    if not rows:
        return
    cols = cols or list(rows[0].keys())
    path = os.path.join(FINAL, name)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("   -> %s (%d rows)" % (name, len(rows)))


def money(x):
    if x is None:
        return "-"
    if abs(x) >= 1e9:
        return "$%.2fB" % (x / 1e9)
    if abs(x) >= 1e6:
        return "$%.1fM" % (x / 1e6)
    return "$%,.0f".replace("%,", "%") % x


def fmt(x):
    if x is None:
        return "-"
    if abs(x) >= 1e9:
        return "$%.2fB" % (x / 1e9)
    if abs(x) >= 1e6:
        return "$%.1fM" % (x / 1e6)
    return "${:,.0f}".format(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default=os.path.join(FINAL, "md_it_contracts.csv"))
    ap.add_argument("--rollup", default=os.path.join(FINAL, "md_it_contract_rollup.csv"))
    args = ap.parse_args()

    items = read(args.items)
    rollup = read(args.rollup)
    for r in items:
        r["year"] = int((r["meeting_date"] or "0000")[:4] or 0)
        r["amount"] = num(r["amount_usd"]) or 0.0

    # ---------------------------------------------------------------- Q1 ---
    print("\nQ1  Approved IT contract value by year")
    # Split out task orders bundled inside an item. The summaries only began
    # listing those as numbered sub-items around 2020, so a single total per
    # year is not comparable across that boundary and the two parts are kept
    # apart rather than added and hoped for.
    by_year = defaultdict(lambda: {"amount": 0.0, "items": 0,
                                   "sub_amount": 0.0, "sub_items": 0})
    for r in items:
        bucket = by_year[r["year"]]
        if r.get("parent_item"):
            bucket["sub_amount"] += r["amount"]
            bucket["sub_items"] += 1
        else:
            bucket["amount"] += r["amount"]
            bucket["items"] += 1
    q1 = [{"year": y,
           "approved_usd_agenda_items": round(v["amount"], 2),
           "approved_usd_bundled_task_orders": round(v["sub_amount"], 2),
           "approved_usd": round(v["amount"] + v["sub_amount"], 2),
           "agenda_items": v["items"], "bundled_task_orders": v["sub_items"]}
          for y, v in sorted(by_year.items()) if y]
    for row in q1:
        print("   %d  %12s  %4d items  + %11s in %3d bundled task orders"
              % (row["year"], fmt(row["approved_usd_agenda_items"]),
                 row["agenda_items"],
                 fmt(row["approved_usd_bundled_task_orders"]),
                 row["bundled_task_orders"]))
    write("analysis_q1_by_year.csv", q1)

    by_agency = defaultdict(lambda: {"amount": 0.0, "items": 0})
    for r in items:
        key = (r["agency"] or "unknown").split("/")[0].strip() or "unknown"
        by_agency[key]["amount"] += r["amount"]
        by_agency[key]["items"] += 1
    q1b = sorted(({"agency": k, "approved_usd": round(v["amount"], 2),
                   "items": v["items"]} for k, v in by_agency.items()),
                 key=lambda r: -r["approved_usd"])
    print("   top agencies: " + ", ".join(
        "%s %s" % (r["agency"], fmt(r["approved_usd"])) for r in q1b[:5]))
    write("analysis_q1_by_agency.csv", q1b)

    # ---------------------------------------------------------------- Q2 ---
    print("\nQ2  Top vendors by approved value")
    named = [r for r in items
             if r["vendor_clean"] and int(r["multi_vendor"] or 0) == 0]
    by_vendor = defaultdict(lambda: {"amount": 0.0, "items": 0, "name": ""})
    for r in named:
        bucket = by_vendor[r["vendor_clean"]]
        bucket["amount"] += r["amount"]
        bucket["items"] += 1
        bucket["name"] = r.get("vendor_display") or r["vendor_clean"]
    q2 = sorted(({"vendor": v["name"], "vendor_key": k,
                  "approved_usd": round(v["amount"], 2),
                  "items": v["items"]} for k, v in by_vendor.items()),
                key=lambda r: -r["approved_usd"])
    total = sum(r["approved_usd"] for r in q2)
    top10 = sum(r["approved_usd"] for r in q2[:10])
    print("   %d named vendors, %s in total" % (len(q2), fmt(total)))
    print("   top 10 hold %.1f%% of it" % (100.0 * top10 / total if total else 0))
    for r in q2[:10]:
        print("      %-44s %12s  %3d items"
              % (r["vendor"][:44], fmt(r["approved_usd"]), r["items"]))
    write("analysis_q2_vendors.csv", q2[:200])

    # ------------------------------------------------------------ Q3, Q4 ---
    print("\nQ3  Growth from original award to total approved")
    grown = [r for r in rollup
             if r["in_growth_analysis"] == "1" and num(r["growth_pct"]) is not None]
    pcts = sorted(num(r["growth_pct"]) for r in grown)
    if pcts:
        print("   %d contracts in the analysis" % len(pcts))
        print("   median growth  %6.1f%%" % median(pcts))
        print("   mean growth    %6.1f%%" % (sum(pcts) / len(pcts)))
        changed = [p for p in pcts if abs(p) > 0.01]
        print("   %d of %d (%.0f%%) were modified at all"
              % (len(changed), len(pcts), 100.0 * len(changed) / len(pcts)))
        if changed:
            print("   median growth among those that changed  %.1f%%"
                  % median(changed))

        print("\nQ4  The distribution, not just the median")
        buckets = [("no change", lambda p: abs(p) <= 0.01),
                   ("under 10%", lambda p: 0.01 < p <= 10),
                   ("10 to 25%", lambda p: 10 < p <= 25),
                   ("25 to 50%", lambda p: 25 < p <= 50),
                   ("50 to 100%", lambda p: 50 < p <= 100),
                   ("100 to 300%", lambda p: 100 < p <= 300),
                   ("over 300%", lambda p: p > 300),
                   ("negative", lambda p: p < -0.01)]
        q4 = []
        for label, test in buckets:
            n = sum(1 for p in pcts if test(p))
            q4.append({"bucket": label, "contracts": n,
                       "share_pct": round(100.0 * n / len(pcts), 1)})
            print("   %-13s %4d  %5.1f%%" % (label, n, 100.0 * n / len(pcts)))
        write("analysis_q4_growth_distribution.csv", q4)

        biggest = sorted(grown, key=lambda r: -(num(r["growth_pct"]) or 0))[:15]
        write("analysis_q3_largest_growth.csv",
              [{"contract_id": r["contract_id"], "vendor": r["vendor_clean"],
                "agency": r["agency"],
                "original_approved_usd": r["original_approved_usd"],
                "total_approved_usd": r["total_approved_usd"],
                "growth_pct": r["growth_pct"], "n_changes": r["n_changes"]}
               for r in biggest])
    write("analysis_q3_growth.csv",
          [{"contract_id": r["contract_id"], "vendor": r["vendor_clean"],
            "agency": r["agency"], "first_item_date": r["first_item_date"],
            "original_approved_usd": r["original_approved_usd"],
            "total_approved_usd": r["total_approved_usd"],
            "growth_usd": r["growth_usd"], "growth_pct": r["growth_pct"],
            "n_changes": r["n_changes"],
            "months_to_first_change": r["months_to_first_change"]}
           for r in grown])

    # ---------------------------------------------------------------- Q5 ---
    print("\nQ5  Time from award to first change")
    months = sorted(int(r["months_to_first_change"]) for r in grown
                    if r["months_to_first_change"] not in ("", None))
    if months:
        print("   %d contracts were modified at least once" % len(months))
        print("   median %d months, quartiles %d and %d"
              % (median(months), months[len(months) // 4],
                 months[3 * len(months) // 4]))
        q5 = defaultdict(int)
        for m in months:
            q5[min(m // 6 * 6, 60)] += 1
        write("analysis_q5_months_to_first_change.csv",
              [{"months_bucket_start": k, "contracts": v}
               for k, v in sorted(q5.items())])

    # ---------------------------------------------------------------- Q6 ---
    print("\nQ6  Growth by agency, normalised by contracts let")
    agg = defaultdict(list)
    for r in grown:
        key = (r["agency"] or "unknown").split("/")[0].strip() or "unknown"
        agg[key].append(num(r["growth_pct"]))
    q6 = []
    for key, vals in agg.items():
        if len(vals) < 5:
            continue
        q6.append({"agency": key, "contracts": len(vals),
                   "median_growth_pct": round(median(vals), 1),
                   "share_modified_pct": round(
                       100.0 * sum(1 for v in vals if abs(v) > 0.01) / len(vals), 1)})
    q6.sort(key=lambda r: -r["median_growth_pct"])
    for r in q6[:10]:
        print("   %-12s %3d contracts  median %6.1f%%  %5.1f%% modified"
              % (r["agency"][:12], r["contracts"], r["median_growth_pct"],
                 r["share_modified_pct"]))
    write("analysis_q6_by_agency.csv", q6)


if __name__ == "__main__":
    main()
