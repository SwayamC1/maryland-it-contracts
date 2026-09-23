"""
Turn parsed agenda items into the published IT contract dataset.

Three jobs: decide what counts as an IT item, resolve vendor names, and drop
what should not be counted. Everything it drops it writes down.
"""

import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from vendors import (apply_decisions, load_decisions,
                     looks_like_description, normalise, propose_merges)

# An item is IT if any of three things is true. The third matters more than it
# looks: the Comptroller's own dataset types 731 rows as "Information
# Technology Contract" that carry no agenda item number at all, and in the
# summaries those items are identifiable only by how their description opens.
IT_ITEM_NO = re.compile(r"(?:^|-)IT(?:-|$)", re.I)
IT_AGENDA = re.compile(r"information technology", re.I)
IT_DESCRIPTION = re.compile(r"^\s*Information Technology\b", re.I)

APPROVED = re.compile(r"^approved", re.I)

# The item number usually says what kind of item it is - 3-IT-MOD, 6-IT-OPT -
# but a sub-item has no suffix of its own and some parent items carry the kind
# only in the description ("Information Technology Option/Modificaiton - ...",
# typo and all). So the description is read too, and a modification beats a
# renewal when an item is both.
PARENTHETICAL = re.compile(r"\([^)]*\)")
# The tail a wrapped vendor name loses to the line break. Only these count:
# anything else that follows a shorter spelling is a different name, or the
# parser having dragged something into the column that does not belong.
LEGAL_FORMS = {"inc", "inc.", "llc", "llp", "lp", "ltd", "co", "corp",
               "corporation", "incorporated", "plc", "pc", "pa", "company",
               "l l c", "lllp"}
TYPE_RULES = [
    # "Modificaiton" is the state's own recurring typo and it appears often
    # enough to be worth matching.
    ("modification",
     re.compile(r"(?:^|-)MOD\b|\bModifica(?:ti|it)ons?\b", re.I)),
    ("renewal", re.compile(r"(?:^|-)OPT\b|\bRenewal Option\b|"
                           r"\bexercis\w+[^.]{0,40}\boption\b", re.I)),
    ("confirmation", re.compile(r"\bconfirm", re.I)),
]


def classify_type(row):
    """award / modification / renewal / confirmation.

    The description is read with parentheses removed first. Without that, an
    ordinary award whose term reads "(w/two 1-year renewal options)" is typed
    as a renewal - which is what happened to the ECCATS project manager award
    in the hand audit.
    """
    # The item number is read first and on its own. An item numbered 1-IT-OPT
    # is a renewal even though its description says "Modification Amount:
    # $165,580" further down, because the Board numbered it OPT; reading both
    # together let the word "Modification" in a money label outvote the
    # number. An item numbered -OPTMOD is both, and modification wins, which is
    # why the rules are ordered the way they are.
    number = row.get("doc_number") or ""
    for name, pattern in TYPE_RULES:
        if pattern.search(number):
            return name
    description = PARENTHETICAL.sub(" ", row.get("description") or "")
    for name, pattern in TYPE_RULES:
        if pattern.search(description):
            return name
    return "award"


def classify_it(row):
    # A sub-item inherits its parent's classification. "29-IT 1.1" is a task
    # order under an IT item; its own description reads "Modification - MVA Web
    # Focus Support" and gives nothing away.
    return int(bool(IT_ITEM_NO.search(row.get("doc_number") or ""))
               or bool(IT_ITEM_NO.search(row.get("parent_item") or ""))
               or bool(IT_AGENDA.search(row.get("agenda") or ""))
               or bool(IT_DESCRIPTION.search(row.get("description") or "")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/interim/items_all.csv")
    ap.add_argument("--merges", default="data/interim/vendor_merges.csv")
    ap.add_argument("--out", default="data/final/md_it_contracts.csv")
    ap.add_argument("--drops", default="data/final/md_it_dropped_items.csv")
    ap.add_argument("--propose", action="store_true",
                    help="write a fresh vendor merge proposal file and stop")
    args = ap.parse_args()

    with open(args.items, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["is_it"] = classify_it(r)
        r["item_type"] = classify_type(r)

    it = [r for r in rows if r["is_it"]]
    print("%d items parsed, %d of them IT" % (len(rows), len(it)))

    if args.propose or not os.path.exists(args.merges):
        names = [normalise(r["vendor_raw"]) for r in it
                 if normalise(r["vendor_raw"])
                 and not looks_like_description(r["vendor_raw"])
                 and not (r["vendor_raw"] or "").strip().startswith(("..", "--"))]
        proposals = propose_merges(names, threshold=88)
        os.makedirs(os.path.dirname(args.merges), exist_ok=True)
        with open(args.merges, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["keep", "canonical", "alias",
                                               "score", "canonical_items",
                                               "alias_items"])
            w.writeheader()
            w.writerows(proposals)
        print("wrote %d proposed vendor merges to %s - review keep=0/1 there"
              % (len(proposals), args.merges))
        if args.propose:
            return

    decisions = load_decisions(args.merges)
    print("%d vendor merges applied" % len(decisions))

    keep, drops = [], []
    for r in it:
        reason = None
        if not r["action"]:
            reason = "no action line found in the summary"
        elif not APPROVED.match(r["action"] or ""):
            reason = "Board action was %r, not approved" % r["action"]
        elif r["amount_basis"] == "revenue-to-state":
            reason = "revenue to the state, not an expenditure"
        elif r["amount_usd"] in (None, ""):
            reason = ("no dollar figure on the item"
                      if r["amount_basis"] != "no change"
                      else "term-only change, no dollar figure")
        if reason:
            drops.append({**r, "drop_reason": reason})
        else:
            # ".." and "--" are what the summaries print in the vendor column
            # when an item has no single vendor - a master contract award, or a
            # table of sub-items. Anything whose vendor column STARTS with one
            # is unattributable no matter what text follows it, because what
            # follows is a list.
            raw = (r["vendor_raw"] or "").strip()
            # "Various" is the third placeholder the summaries use for an item
            # that has no single vendor, and unlike ".." it is followed by the
            # list of companies rather than standing alone. It is printed
            # "Various" on some pages and "VARIOUS" on others, so the test is
            # case-insensitive - it was not, and the shouted spelling let a
            # pool of fourteen master contractors through as one vendor.
            if raw.startswith(("..", "--")) \
                    or raw.lower().startswith("various") \
                    or looks_like_description(raw):
                r["vendor_clean"] = ""
                r["multi_vendor"] = 1
            else:
                r["vendor_clean"] = apply_decisions(raw, decisions) or ""
            keep.append(r)

    # A readable label for each resolved vendor: the spelling that appears most
    # often in the documents, rather than the normalised matching key. The key
    # is for joining; nobody wants to read "shi" on a chart.
    spellings = {}
    for r in keep:
        if r["vendor_clean"]:
            counts = spellings.setdefault(r["vendor_clean"], {})
            raw = " ".join((r["vendor_raw"] or "").split())
            counts[raw] = counts.get(raw, 0) + 1
    # Pick the label by frequency, but first throw out any spelling that is the
    # same name with its legal form missing. A vendor name that wraps onto the
    # next line loses its last word - "Business Solutions Group," for "Business
    # Solutions Group, LLC" - and because the wrap happens on most of that
    # vendor's rows the truncated form is the more common one and wins a plain
    # vote. Only a legal form counts as the missing tail: dropping every
    # spelling that is a prefix of a longer one promotes the corrupted
    # spellings instead, which is how "NEC Corporation of America" lost to
    # "NEC Corporation of America remaining".
    display = {}
    for key, counts in spellings.items():
        names = list(counts)
        truncated = set()
        for short in names:
            for long in names:
                if long != short and long.startswith(short):
                    tail = long[len(short):].strip(" ,.").lower()
                    if tail.replace(".", "") in LEGAL_FORMS:
                        truncated.add(short)
        full = [n for n in names if n not in truncated]
        display[key] = max(full or names,
                           key=lambda s: (counts[s], len(s)))
    for r in keep:
        r["vendor_display"] = display.get(r["vendor_clean"], r["vendor_raw"])

    cols = ["meeting_date", "agenda", "doc_number", "item_type", "agency",
            "county", "vendor_raw", "vendor_clean", "vendor_display",
            "description",
            "amount_usd", "amount_basis", "term_start", "term_end", "action",
            "discussion", "references_doc", "contract_id", "multi_vendor",
            "parent_item", "action_note", "source_pdf", "source_page"]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(keep, key=lambda r: (r["meeting_date"] or "",
                                                r["doc_number"] or "")))
    with open(args.drops, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols + ["drop_reason"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(drops)

    print("kept %d IT items, dropped %d" % (len(keep), len(drops)))
    by_reason = {}
    for d in drops:
        key = d["drop_reason"].split(",")[0][:48]
        by_reason[key] = by_reason.get(key, 0) + 1
    for k, n in sorted(by_reason.items(), key=lambda kv: -kv[1]):
        print("   %4d  %s" % (n, k))
    print("distinct vendors after resolution: %d"
          % len({r["vendor_clean"] for r in keep if r["vendor_clean"]}))


if __name__ == "__main__":
    main()
