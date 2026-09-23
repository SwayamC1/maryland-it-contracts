"""
Build the hand-audit worksheet for the pre-2022 years.

The Comptroller's dataset starts in December 2022, so for 2016 to 2022 there is
no answer key and the benchmark in validate.py says nothing. The only way to
put a number on those years is to open the PDFs and read them.

This script does the sampling and pulls the printed text that surrounds each
sampled item, so that the reading is against the document rather than against
a memory of it. It writes two files:

    data/final/hand_audit_pre2022.csv        the worksheet, verdicts blank
    data/final/hand_audit_pre2022_scored.csv is NOT written here - it is the
                                             worksheet after a human fills in
                                             the verdict columns, and it is
                                             committed by hand.

The seed is fixed and recorded in the output so the sample can be rebuilt.
"""

import argparse
import csv
import hashlib
import json
import os
import sys

import pdfplumber

FIELDS = ["meeting_date", "agency", "county", "vendor", "amount",
          "term", "item_type", "action"]


def printed_text(pdf_path, page_no, doc_number, window=620):
    """The text printed around an item, as the page prints it."""
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[int(page_no) - 1]
        text = " ".join((page.extract_text() or "").split())
    key = doc_number.split(" ")[-1] if " " in doc_number else doc_number
    idx = text.find(key)
    if idx < 0:
        idx = 0
    start = max(0, idx - 120)
    return text[start:start + window]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/final/md_it_contracts.csv")
    ap.add_argument("--pdfs", default="data/raw/summaries")
    ap.add_argument("--out", default="data/final/hand_audit_pre2022.csv")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20260916)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    with open(args.items, newline="") as fh:
        rows = [r for r in csv.DictReader(fh)
                if (r["meeting_date"] or "9999") < "2022-01-01"]
    print("%d IT items before 2022" % len(rows))

    # Choose by hashing each item's own identity rather than by position in
    # the file. random.sample draws a different 100 every time the dataset
    # gains or loses a row, which would throw away the reading already done;
    # hashing keeps the same items in the sample as long as those items exist.
    def ticket(row):
        key = "%s|%s|%s|%s" % (args.seed, row["meeting_date"],
                               row["doc_number"], row["source_pdf"])
        return hashlib.md5(key.encode()).hexdigest()

    sample = sorted(rows, key=ticket)[:args.n]
    sample.sort(key=lambda r: (r["meeting_date"], r["doc_number"]))

    out = []
    for i, r in enumerate(sample, 1):
        path = os.path.join(args.pdfs, r["source_pdf"])
        try:
            printed = printed_text(path, r["source_page"], r["doc_number"])
        except Exception as exc:                      # noqa: BLE001
            printed = "COULD NOT READ PAGE: %s" % exc
        row = {
            "n": i, "seed": args.seed,
            "meeting_date": r["meeting_date"], "doc_number": r["doc_number"],
            "source_pdf": r["source_pdf"], "source_page": r["source_page"],
            "parsed_agency": r["agency"], "parsed_county": r["county"],
            "parsed_vendor": r["vendor_display"] or r["vendor_raw"],
            "parsed_amount": r["amount_usd"],
            "parsed_term": "%s..%s" % (r["term_start"] or "",
                                       r["term_end"] or ""),
            "parsed_item_type": r["item_type"],
            "parsed_action": r["action"],
            "printed_text": printed,
        }
        for f in FIELDS:
            row["ok_" + f] = ""
        row["note"] = ""
        out.append(row)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cols = list(out[0].keys())
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print("wrote %s (%d rows, verdict columns blank)" % (args.out, len(out)))

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % args.json)


if __name__ == "__main__":
    sys.exit(main())
