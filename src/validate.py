"""
Benchmark the extraction against the Comptroller's own dataset.

This is the step that makes the project worth anything. The Office of the
Comptroller publishes structured BPW data from December 2022 onward; my
pipeline processed the same meetings from the PDFs. Where they overlap, their
file is the answer key.

Two things about that answer key, both found by reading it rather than assuming:

  * It changes schema partway through. Rows from 2022, 2025 and 2026 carry an
    Agenda Item Number ("DGS 17-IT") and types like "Information Technology
    Modification". Rows from 2023 and 2024 carry NO item number at all and are
    typed "Information Technology Contract". Any matching rule that leans on
    the item number silently loses two whole years.
  * Every IT row carries a Contract value, sometimes several separated by ";"
    or "/", and sometimes the literal string "No Contract Number Listed".

So matching runs in three passes, strongest key first: meeting date plus item
number, then meeting date plus a shared contract number, then meeting date plus
vendor and amount. Every row that survives all three unmatched is written out
to be opened by hand.
"""

import argparse
import csv
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from vendors import normalise

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
          "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
          "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
          "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
          "dec": 12, "december": 12}

LINK_DATE = re.compile(r"/MeetingDocs/(\d{4})-([A-Za-z]+)-(\d{1,2})-", re.I)
IT_TYPE = re.compile(r"information technology", re.I)
NO_CONTRACT = re.compile(r"no contract number", re.I)
ITEM_SUFFIX = re.compile(r"([0-9]+[A-Z]?(?:-[A-Z0-9]{1,8}){0,3})\s*$")


def link_date(url):
    m = LINK_DATE.search(url or "")
    if not m:
        return None
    month = m.group(2).lower()
    if month not in MONTHS:
        return None
    return "%s-%02d-%02d" % (m.group(1), MONTHS[month], int(m.group(3)))


def contract_keys(value):
    """'060B2490023; M00B0600012 / CTR020948' -> {'060B2490023', 'M00B0600012', 'CTR020948'}"""
    if not value or NO_CONTRACT.search(value):
        return set()
    parts = re.split(r"[;/,]| and ", value)
    return {p.strip().upper() for p in parts if len(p.strip()) >= 5}


def money(value):
    try:
        return round(float(str(value).replace(",", "").replace("$", "")), 2)
    except (TypeError, ValueError):
        return None


def close(a, b, tol=0.01):
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return True
    return abs(a - b) <= max(tol, 0.005 * max(abs(a), abs(b)))


def collapse_zero_rows(rows):
    """Fold the Comptroller's multi-vendor rows back into one row per item.

    When the Board approves one master contract with many awardees, their
    dataset prints one row per company: the first carries the whole amount and
    the rest carry 0.00. Compared row for row against a dataset that keeps one
    row per approval, that looks like a recall failure and is not one. Rows
    sharing a meeting, an item number and a contract are folded together, with
    the vendors joined.
    """
    groups = defaultdict(list)
    singles = []
    for r in rows:
        item = (r["Agenda Item Number"] or "").strip()
        if item:
            groups[(r["meeting_date"], item, r["Contract"])].append(r)
        else:
            singles.append(r)

    out = list(singles)
    folded = 0
    for members in groups.values():
        nonzero = [m for m in members if money(m["Amount"])]
        if len(members) > 1 and len(nonzero) == 1:
            keep = dict(nonzero[0])
            keep["Recipient"] = "; ".join(
                dict.fromkeys(m["Recipient"] for m in members if m["Recipient"]))
            out.append(keep)
            folded += len(members) - 1
        else:
            out.extend(members)
    if folded:
        print("folded %d zero-amount duplicate rows into their siblings"
              % folded)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", default="data/final/md_it_contracts.csv")
    ap.add_argument("--truth", default="data/raw/comptroller_bpw_dataset.csv")
    ap.add_argument("--outdir", default="data/final")
    args = ap.parse_args()

    with open(args.mine, newline="") as fh:
        mine_all = list(csv.DictReader(fh))
    with open(args.truth, newline="") as fh:
        truth_all = list(csv.DictReader(fh))

    for t in truth_all:
        t["meeting_date"] = link_date(t["Agenda Link"])
    truth = collapse_zero_rows(
        [t for t in truth_all
         if IT_TYPE.search(t["Type"] or "") and t["meeting_date"]])
    first = min(t["meeting_date"] for t in truth)
    last = max(t["meeting_date"] for t in truth)
    mine = [m for m in mine_all if m["meeting_date"]
            and first <= m["meeting_date"] <= last]

    print("overlap window %s to %s" % (first, last))
    print("their IT rows: %d      my IT items in the same window: %d"
          % (len(truth), len(mine)))

    by_date = defaultdict(list)
    for m in mine:
        by_date[m["meeting_date"]].append(m)

    matched_pairs, used = [], set()
    for t in truth:
        pool = [m for m in by_date.get(t["meeting_date"], [])
                if id(m) not in used]
        hit = how = None

        item = ITEM_SUFFIX.search((t["Agenda Item Number"] or "").strip())
        if item:
            want = item.group(1).upper()
            cands = [m for m in pool if (m["doc_number"] or "").upper() == want]
            if len(cands) == 1:
                hit, how = cands[0], "item number"

        if hit is None:
            keys = contract_keys(t["Contract"])
            if keys:
                cands = [m for m in pool
                         if contract_keys(m["contract_id"]) & keys]
                if len(cands) == 1:
                    hit, how = cands[0], "contract number"

        if hit is None:
            amount = money(t["Amount"])
            vendor = normalise(t["Recipient"])
            cands = [m for m in pool
                     if close(money(m["amount_usd"]), amount)
                     and vendor and normalise(m["vendor_raw"]) == vendor]
            if len(cands) == 1:
                hit, how = cands[0], "vendor and amount"

        if hit is not None:
            used.add(id(hit))
            matched_pairs.append((t, hit, how))

    # Some meetings posted a Summary before the meeting and never updated it
    # with the Board's actions. Those documents do not contain the information
    # this pipeline reads, so recall is reported twice: over everything, and
    # over the meetings whose summaries actually record actions.
    actioned = {m["meeting_date"] for m in mine_all if (m["action"] or "").strip()}
    truth_actioned = [t for t in truth if t["meeting_date"] in actioned]
    matched_actioned = [p for p in matched_pairs
                        if p[0]["meeting_date"] in actioned]
    recall_actioned = (100.0 * len(matched_actioned)
                       / max(len(truth_actioned), 1))

    recall = 100.0 * len(matched_pairs) / max(len(truth), 1)
    precision = 100.0 * len(matched_pairs) / max(len(mine), 1)
    print("\nrecall    %5.1f%%   (%d of their %d IT rows found)"
          % (recall, len(matched_pairs), len(truth)))
    print("recall    %5.1f%%   on meetings whose summary records actions "
          "(%d of %d)" % (recall_actioned, len(matched_actioned),
                          len(truth_actioned)))
    print("precision %5.1f%%   (%d of my %d IT items matched one of theirs)"
          % (precision, len(matched_pairs), len(mine)))
    how_counts = defaultdict(int)
    for _, _, how in matched_pairs:
        how_counts[how] += 1
    for how, n in sorted(how_counts.items(), key=lambda kv: -kv[1]):
        print("   matched on %-18s %d" % (how, n))

    fields = {"amount": 0, "vendor": 0, "contract": 0, "meeting_date": 0}
    counted = {k: 0 for k in fields}
    disagreements = []
    for t, m, how in matched_pairs:
        ta, ma = money(t["Amount"]), money(m["amount_usd"])
        if ta is not None and ma is not None:
            counted["amount"] += 1
            if close(ma, ta):
                fields["amount"] += 1
            else:
                disagreements.append({
                    "field": "amount", "meeting_date": t["meeting_date"],
                    "item": t["Agenda Item Number"], "matched_on": how,
                    "theirs": t["Amount"], "mine": m["amount_usd"],
                    "source_pdf": m["source_pdf"], "source_page": m["source_page"]})
        tv, mv = normalise(t["Recipient"]), normalise(m["vendor_raw"])
        if tv and mv:
            counted["vendor"] += 1
            if tv == mv or tv in mv or mv in tv:
                fields["vendor"] += 1
            else:
                disagreements.append({
                    "field": "vendor", "meeting_date": t["meeting_date"],
                    "item": t["Agenda Item Number"], "matched_on": how,
                    "theirs": t["Recipient"], "mine": m["vendor_raw"],
                    "source_pdf": m["source_pdf"], "source_page": m["source_page"]})
        tk, mk = contract_keys(t["Contract"]), contract_keys(m["contract_id"])
        if tk and mk:
            counted["contract"] += 1
            if tk & mk:
                fields["contract"] += 1
            else:
                disagreements.append({
                    "field": "contract", "meeting_date": t["meeting_date"],
                    "item": t["Agenda Item Number"], "matched_on": how,
                    "theirs": t["Contract"], "mine": m["contract_id"],
                    "source_pdf": m["source_pdf"], "source_page": m["source_page"]})
        counted["meeting_date"] += 1
        fields["meeting_date"] += 1

    print("\nfield agreement on matched rows")
    for k in ("meeting_date", "amount", "vendor", "contract"):
        if counted[k]:
            print("   %-14s %5.1f%%   (%d of %d comparable)"
                  % (k, 100.0 * fields[k] / counted[k], fields[k], counted[k]))

    os.makedirs(args.outdir, exist_ok=True)
    matched_ids = {id(m) for _, m, _ in matched_pairs}
    misses = [t for t in truth
              if not any(t is tt for tt, _, _ in matched_pairs)]
    extras = [m for m in mine if id(m) not in matched_ids]

    with open(os.path.join(args.outdir, "validation_misses.csv"), "w",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(truth[0].keys()))
        w.writeheader()
        w.writerows(misses)
    with open(os.path.join(args.outdir, "validation_extras.csv"), "w",
              newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mine[0].keys()))
        w.writeheader()
        w.writerows(extras)
    if disagreements:
        with open(os.path.join(args.outdir, "validation_disagreements.csv"),
                  "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(disagreements[0].keys()))
            w.writeheader()
            w.writerows(disagreements)

    with open(os.path.join(args.outdir, "validation_summary.csv"), "w",
              newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["measure", "value", "numerator", "denominator"])
        w.writerow(["recall_pct", round(recall, 2), len(matched_pairs), len(truth)])
        w.writerow(["recall_actioned_meetings_pct", round(recall_actioned, 2),
                    len(matched_actioned), len(truth_actioned)])
        w.writerow(["precision_pct", round(precision, 2), len(matched_pairs), len(mine)])
        for k in ("meeting_date", "amount", "vendor", "contract"):
            if counted[k]:
                w.writerow(["%s_agreement_pct" % k,
                            round(100.0 * fields[k] / counted[k], 2),
                            fields[k], counted[k]])

    print("\nwrote validation_summary.csv, %d misses, %d extras, %d field disagreements"
          % (len(misses), len(extras), len(disagreements)))


if __name__ == "__main__":
    main()
