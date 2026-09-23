"""
Link modifications back to the award they change, and roll each contract up.

The join key is the state's own document number, printed on the action line as
"Doc. No." and captured as contract_id. Where an item has none, references_doc
- cross references pulled out of the description text - is the fallback.

Two scope rules, both of which have to be stated or the growth figure is
misleading:

  1. A contract can only be measured if its ORIGINAL AWARD is inside the
     window. A modification whose award was approved in 2014 shows up as a
     contract that is 100% modification and 0% award, which would read as
     infinite growth. Those are dropped and listed.
  2. A contract needs time to grow. One awarded in 2026 has had months, not
     years, to be modified. The growth analysis is cut at awards made through
     2022 so every contract in it has had at least three years.

And the caveat the whole project rests on: these are APPROVED CEILINGS, not
money spent. "Not to Exceed $390,000" means the state may spend up to that.
Every column name here says approved for that reason.
"""

import argparse
import csv
import os
import re
from collections import defaultdict

AWARD_TYPES = {"award", "confirmation"}

# Maryland uses two identifier systems at once. An award is printed with its
# procurement contract number (F50B2600034); a later modification is very often
# printed with a change-order control number instead (COL26444), and the
# Summary does not print the contract number anywhere on that item. 301 of 466
# modifications in this dataset carry a control number of that kind, which is
# why most modifications cannot be linked to the contract they modify from the
# Summaries alone. That is a finding about the published record, not a parsing
# failure, and it is the main limitation of this project.
#
# The Comptroller's dataset does sometimes print both, separated by a slash, so
# it can be used as a crosswalk - but only from December 2022 onward, which is
# exactly the period this project exists to reach past.
CONTROL_NUMBER = re.compile(r"^(?:CTR|CO[A-Z])[A-Z0-9\-]*$", re.I)
CONTRACT_NUMBER = re.compile(r"^[0-9A-Z]{3,}[A-Z]?\d{5,}[A-Z0-9\-]*$", re.I)


def load_crosswalk(path):
    """control number -> contract number, from the Comptroller's Contract field."""
    if not os.path.exists(path):
        return {}
    pairs = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            value = row.get("Contract") or ""
            parts = [p.strip() for p in re.split(r"[;/,]", value) if p.strip()]
            controls = [p for p in parts if CONTROL_NUMBER.match(p)]
            contracts = [p for p in parts
                         if CONTRACT_NUMBER.match(p) and not CONTROL_NUMBER.match(p)]
            if len(controls) >= 1 and len(contracts) == 1:
                for c in controls:
                    pairs.setdefault(c.upper(), contracts[0].upper())
    return pairs


def money(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/final/md_it_contracts.csv")
    ap.add_argument("--out", default="data/final/md_it_contract_rollup.csv")
    ap.add_argument("--drops", default="data/final/md_it_rollup_dropped.csv")
    ap.add_argument("--growth-cutoff", type=int, default=2022,
                    help="last award year allowed into the growth analysis")
    ap.add_argument("--crosswalk",
                    default="data/raw/comptroller_bpw_dataset.csv")
    args = ap.parse_args()

    with open(args.items, newline="") as fh:
        rows = list(csv.DictReader(fh))

    crosswalk = load_crosswalk(args.crosswalk)
    resolved = 0

    groups = defaultdict(list)
    unkeyed = []
    for r in rows:
        key = (r["contract_id"] or "").strip().upper()
        if key in crosswalk:
            key = crosswalk[key]
            resolved += 1
        if not key:
            first_ref = (r["references_doc"] or "").split(";")[0].strip().upper()
            key = first_ref
        if key:
            groups[key].append(r)
        else:
            unkeyed.append(r)

    rollups, drops = [], []
    for key, items in groups.items():
        items.sort(key=lambda r: r["meeting_date"] or "")
        awards = [i for i in items if i["item_type"] in AWARD_TYPES]
        changes = [i for i in items if i["item_type"] not in AWARD_TYPES]

        total = sum(money(i["amount_usd"]) or 0 for i in items)
        row = {
            "contract_id": key,
            "agency": items[0]["agency"],
            "vendor_clean": items[0]["vendor_clean"] or items[0]["vendor_raw"],
            "n_items": len(items),
            "n_awards": len(awards),
            "n_changes": len(changes),
            "first_item_date": items[0]["meeting_date"],
            "last_item_date": items[-1]["meeting_date"],
            "original_approved_usd": None,
            "later_approved_usd": round(sum(money(i["amount_usd"]) or 0
                                            for i in changes), 2),
            "total_approved_usd": round(total, 2),
            "growth_usd": None,
            "growth_pct": None,
            "months_to_first_change": None,
            "in_growth_analysis": 0,
            "exclusion_reason": "",
            "multi_vendor": max(int(i["multi_vendor"] or 0) for i in items),
        }

        if not awards:
            row["exclusion_reason"] = ("no original award inside the window - "
                                       "only later changes were captured")
        else:
            first = awards[0]
            original = money(first["amount_usd"])
            row["original_approved_usd"] = original
            if original:
                row["growth_usd"] = round(total - original, 2)
                row["growth_pct"] = round(100.0 * (total - original) / original, 2)
            if changes:
                row["months_to_first_change"] = months_between(
                    first["meeting_date"], changes[0]["meeting_date"])
            award_year = int((first["meeting_date"] or "0000")[:4] or 0)
            if not original:
                row["exclusion_reason"] = "original award has no dollar figure"
            elif award_year > args.growth_cutoff:
                row["exclusion_reason"] = (
                    "awarded in %d, after the %d cutoff - not enough time to "
                    "have been modified" % (award_year, args.growth_cutoff))
            elif row["multi_vendor"]:
                row["exclusion_reason"] = ("item covers several vendors, so the "
                                           "money is not one contract's")
            else:
                row["in_growth_analysis"] = 1

        (rollups if row["in_growth_analysis"] else drops).append(row)

    cols = list((rollups or drops)[0].keys())
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(rollups + drops,
                           key=lambda r: (-(r["total_approved_usd"] or 0))))
    with open(args.drops, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(sorted(drops, key=lambda r: r["contract_id"]))

    grew = [r for r in rollups if r["growth_pct"] is not None]
    grew.sort(key=lambda r: r["growth_pct"])
    control_only = sum(1 for r in rows
                       if CONTROL_NUMBER.match((r["contract_id"] or "").strip()))
    print("%d items, %d with a usable key, %d with none"
          % (len(rows), len(rows) - len(unkeyed), len(unkeyed)))
    print("%d items carry a change-order control number rather than a contract "
          "number; %d of those were resolved through the Comptroller crosswalk"
          % (control_only, resolved))
    print("%d contracts, %d in the growth analysis, %d excluded"
          % (len(groups), len(rollups), len(drops)))
    if grew:
        mid = grew[len(grew) // 2]
        print("median growth from original award to total approved: %.1f%%"
              % mid["growth_pct"])
        print("contracts that grew at all: %d of %d"
              % (sum(1 for r in grew if r["growth_pct"] > 0.01), len(grew)))
    reasons = defaultdict(int)
    for d in drops:
        reasons[d["exclusion_reason"].split("-")[0].strip()[:52]] += 1
    for k, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print("   %4d excluded: %s" % (n, k))


def months_between(a, b):
    if not a or not b:
        return None
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    return (yb - ya) * 12 + (mb - ma)


if __name__ == "__main__":
    main()
