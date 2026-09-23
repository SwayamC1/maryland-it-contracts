"""
Board of Public Works meeting Summary PDFs -> one row per agenda item.

The plan for this project assumed the summaries were ruled tables and that
pdfplumber's extract_table() would carry most of the work. It does not:
extract_table() returns ZERO rows on every summary I tried, 2017 through 2026.
The summaries are positioned text in five unruled columns, which is why the
deterministic share of this pipeline is not "80% of rows parse as a table" but
"100% of rows parse from word coordinates". That is a better answer and it is
the honest one; docs/source-notes.md records how it was checked.

Layout, stable across the whole 2016-2026 window:

    Item   Agency/Institution   County   Vendor, Contractor, Grantee   Description
    x<100      100-185          185-272            272-445               >=445

An item begins on a line with something in the Item column, runs across as many
lines as it needs, and is closed by a line starting "action:" which carries the
Board's action, whether there was discussion, and - crucially - the state's own
document number. That document number is the join key between an award and the
modifications that follow it years later.

Three structural details worth knowing, all of which broke a first draft:

  * The action line for an item can appear at the TOP of the next page, after
    the repeated column header. So an action line with no open item belongs to
    the item that was closed most recently and does not yet have one.
  * Vendor names wrap. "Emjay Engineering and Construction / Co., Inc." is two
    printed lines and one company.
  * A single item can award fifteen task orders at once, each printed as a
    numbered SUB-ITEM with its own agency, vendor, document number and amount.
    Those are emitted as their own rows. Without them this dataset sits at a
    coarser grain than the state's own and recovers only a third of it - which
    is exactly what the first validation run showed.
"""

import argparse
import csv
import glob
import os
import re
from statistics import median

import pdfplumber

# Column boundaries, taken from the header row when it is present on the page
# and falling back to these when it is not.
DEFAULT_BOUNDS = (100.0, 185.0, 272.0, 445.0)

HEADER_WORDS = ("Item", "County", "Vendor,", "Description")

ITEM_NO = re.compile(r"^(?:A)?\d+[A-Z]?(?:-[A-Z0-9]{1,8}){0,3}$")
# "Doc. No." is printed on every action line, with the number missing on items
# that have no state contract number, so the number itself has to be optional.
# The Board sometimes writes a note after the document number - most usefully
# "Sub-Item 5.1 was withdrawn at the meeting", which withdraws one task order
# out of fifteen. An earlier version of this pattern required the line to end
# at the document number, so every item carrying such a note lost its action
# and took all of its sub-items down with it.
ACTION_LINE = re.compile(r"^action:\s*(?P<action>.+?)\s+discussion:\s*"
                         r"(?P<discussion>\S+)"
                         r"(?:\s+Doc\.\s*No\.?\s*"
                         # case-sensitive on purpose: the whole pattern runs
                         # case-insensitive, and without this "Sub-Item" reads
                         # as a document number
                         r"(?P<doc>(?-i:[A-Z0-9][A-Z0-9/\-]{3,}))?)?"
                         r"\s*(?P<note>.*?)\s*$", re.I)
WITHDRAWN_SUB = re.compile(r"sub[- ]?item\s+(\d+\.\d+)\s+was\s+withdrawn",
                           re.I)
ACTION_START = re.compile(r"^action:", re.I)
# The word an action wraps onto when it does not fit the column.
ACTION_TAIL = re.compile(r"^(?:revisions?|amendments?|corrections?|"
                         r"conditions?|modifications?)$", re.I)
DISCUSSION_START = re.compile(r"^discussion:", re.I)
AGENDA_LINE = re.compile(r"^Agenda\s*:?\s*(?P<name>.+?)\s*$")

TERM = re.compile(r"Term:\s*(?P<start>\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*"
                  r"(?P<end>\d{1,2}/\d{1,2}/\d{2,4})")
MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.\d{2})?)")
# The words that mark one half of a two-part approval.
PART_LABEL = re.compile(r"\b(retroactive|proactive|extension)\b", re.I)
AMOUNT_LABEL = re.compile(
    # "Revenue Amount" is listed before "Total Amount" on purpose. A resource
    # sharing agreement prints "Revenue Amount: $199,308" - money paid TO the
    # state for letting a carrier put equipment on a state tower - and the
    # shorter "Amount" label matched inside it, so seven such items were being
    # counted as spending.
    r"(?P<label>Revenue Amount|Total Revenue|Total Amount|Total|Amount|"
    r"Revenue|Grant Amount)"
    r"\s*:\s*"
    # Stop at the next label as well as at a full stop. Without the lookahead
    # the first label swallows the rest of the sentence, so "Retroactive
    # Amount: $311,903, Proactive Amount: $732,542, Total Amount: $1,044,445."
    # is read as one match worth $311,903 and the total is never seen.
    r"(?P<tail>(?:(?!\b(?:Revenue Amount|Total Revenue|Total Amount|Total|"
    r"Amount|Revenue|Grant Amount)\s*:)[^.;])*)", re.I)
# A cross reference to some other document: "#DGS-22-300-JOC", "Contract No.
# 060B2490021", "BPW Item 12-IT (4/1/20)".
REFERENCE = re.compile(
    r"(?:#\s*([A-Z0-9][A-Z0-9\-]{4,}))"
    r"|(?:Contract\s+(?:No\.?|Number)\s*([A-Z0-9][A-Z0-9\-]{4,}))"
    r"|(?:BPW\s+Item\s+(\d+-[A-Z0-9\-]+))"
    # A bare Maryland document number printed in the body, e.g. COL27974 or
    # 060B2490021. Deliberately narrow: at least four letters-then-digits or a
    # long digit-led token, so ordinary words and dollar figures cannot match.
    r"|\b((?:CO[A-Z]\d{4,})|(?:[0-9A-Z]{3}[A-Z]\d{7,}))\b", re.I)

# Every page repeats a two-line banner above the table. Left in, its words get
# appended to whichever item is still open across the page break, which is how
# agencies ended up reading "DIT Agency Institution Agency Institution".
PAGE_BANNER = re.compile(r"^Agency\s+\d{1,2}-[A-Za-z]{3,4}-\d{2}\s*$")
PAGE_FOOTER = re.compile(r"Page\s+\d+\s+of\s+\d+\s*$")

# A sub-item inside an item that awards many task orders at once. It is
# printed with its own number in the county column, its own vendor, often its
# own document number, and its amount right-aligned in a column that ordinary
# items do not use at all:
#
#   REV DOT/MVA  1.1  Custom Software Systems  COJ91363  Modification - ...  $1,093,129.72
#   EDUC         1.3  Deloitte Consulting, LLP COK07300  RETROACTIVE - ...  $37,348,164.00
#                1.4(A) Artisys Corporation        <- another vendor on 1.4, no money
#
# This is the grain the Comptroller publishes at. One BPW item can hold fifteen
# of these, which is why item-level rows alone recover only a third of their
# dataset.
SUB_NO = re.compile(r"^\d+\.\d+$")
SUB_NO_VENDOR = re.compile(r"^\d+\.\d+\([A-Z]+\)$")
# The document numbers that appear inside a sub-item row, between its vendor
# and its description. Six digits, not seven: R00B460017 is a real contract
# number on the 2 September 2020 summary and it has six, and at seven it was
# being read as part of the vendor's name.
DOC_TOKEN = re.compile(r"^(?:CO[A-Z]\d{4,}|[0-9A-Z]{3}[A-Z]\d{6,}|[A-Z]{2,}\d{4,})$")

IT_ITEM_NO = re.compile(r"(?:^|-)IT(?:-|$)", re.I)
IT_AGENDA = re.compile(r"information technology", re.I)


def page_bounds(lines, words):
    """Column boundaries for a page, measured from the page itself.

    Two header layouts exist across the window and they are NOT
    interchangeable:

        Item | Institution | County | Vendor, Contractor, Grantee | Description
        Item | Agency      | County | Vendor, Contractor, Grantee | Description

    Assuming the first one is what made eleven meetings - the whole of early
    2019, February 2018, two 2023 meetings and more - parse to zero items, with
    no error, because every word landed in the wrong column. The column totals
    had nothing to check against, so the only thing that caught it was the
    per-meeting IT count printed at the end of a run.

    The left edge of the description column cannot be read off the header
    either: the Description heading sits above its own body in some documents
    and to the left of it in others, and the body's own margin moves between
    documents. So it is measured instead - the description column is the one
    thing on the page with dozens of lines starting at the same x.
    """
    header = None
    for line in lines:
        text = [w["text"] for w in line]
        if all(h in text for h in ("Item", "County", "Vendor,", "Description")):
            header = line
            break
    if header is None:
        return DEFAULT_BOUNDS

    pos = {}
    for i, w in enumerate(header):
        pos.setdefault(w["text"], w["x0"])
    order = [w["text"] for w in header]
    second = order[order.index("Item") + 1]          # Institution, or Agency
    b1 = pos[second] - 8
    b2 = pos["County"] - 8
    b3 = pos["Vendor,"] - 8

    # A page can have TWO description margins, because the task-order tables
    # that appear inside an item indent their own description further right
    # than the main item table does - 452 and 471 on the same page is typical.
    # Taking the more common of the two puts the first word of every main-table
    # description line inside the vendor column, which is how "StreetLight
    # Data, Inc." came out of the hand audit as "StreetLight Data, Inc.
    # Information platform devices." So: find the margins, then take the
    # leftmost one, and only consider margins within 40pt of the most common so
    # that a run of long vendor names cannot be mistaken for one.
    counts = {}
    for w in words:
        if w["x0"] > pos["Vendor,"] + 60:
            counts[round(w["x0"])] = counts.get(round(w["x0"]), 0) + 1
    body = [x for x, n in counts.items() if n >= 3]
    if body:
        mode = max(body, key=lambda x: counts[x])
        b4 = min(x for x in body if x >= mode - 40) - 6
    else:
        b4 = pos["Description"] - 15
    if not (b3 < b4):
        return DEFAULT_BOUNDS
    return (b1, b2, b3, b4)


def lines_of(page):
    """Words grouped into printed lines, top to bottom, left to right."""
    words = page.extract_words()
    if not words:
        return []
    tol = median([w["bottom"] - w["top"] for w in words]) * 0.6
    groups = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if groups and abs(w["top"] - groups[-1][0]) <= tol:
            groups[-1][1].append(w)
        else:
            groups.append((w["top"], [w]))
    return [sorted(g, key=lambda w: w["x0"]) for _, g in groups]


def merge_split_action_lines(lines):
    """Rejoin an action row that the line grouper split in two.

    "action: Approved" and "discussion: No Doc. No. 526SM71430" are one printed
    row, but the two halves are typeset a fraction of a point apart and land in
    separate bands often enough to matter - it cost two thirds of the items
    their action on the first run.
    """
    out = []
    for words in lines:
        text = " ".join(w["text"] for w in words)
        prev = " ".join(w["text"] for w in out[-1]) if out else ""
        if out and DISCUSSION_START.match(text) and ACTION_START.match(prev):
            out[-1] = sorted(out[-1] + words, key=lambda w: w["x0"])
        elif (out and ACTION_START.match(prev) and len(words) == 1
              and words[0]["x0"] < 120 and ACTION_TAIL.match(text)):
            # The action column is narrow, so "approved with revisions" wraps
            # and "revisions" lands on a line of its own under the action. It
            # is not a continuation of anything else on the page: the
            # description column starts 300 points to the right.
            out[-1] = out[-1] + words
        else:
            out.append(words)
    return out


def complete_action(action, note):
    """Put back the word an action lost to the column width.

    The action column is about 150 points wide, so "approved with revisions"
    prints as "approved with" on one line and "revisions" on the next, past the
    discussion and the document number. The reassembled row reads

        action: approved with discussion: yes Doc. No. 060B0600016
        Approved 2-to-1 with revisions; Treasurer voted no. revisions

    and the completing word is the last token of the note. Only a dangling
    "with" is completed, and only from the small set of words the Board
    actually uses, so nothing else is guessed at.
    """
    if not action.lower().endswith(" with"):
        return action
    tail = note.split()[-1].rstrip(".;,") if note.split() else ""
    if ACTION_TAIL.match(tail):
        return "%s %s" % (action, tail.lower())
    return action


def split_sub_agency(left_words, bounds, parent_agency, parent_county):
    """Agency and county for a sub-item row.

    On a sub-item row the whole left-hand block is shifted one column left of
    where the parent item prints it, so the page's own boundaries put the
    county inside the agency column: "ELECTLAW Statewide 1.1 Netorian LLC" came
    out with agency "ELECTLAW Statewide" until the hand audit caught it.

    Splitting on the column line does not work, because the shift is not the
    same width on every page. Splitting on the first word does, because an
    agency code in these documents is one whitespace token - DOT/SHA and
    DOT/MVA included - across all 175 agency values in the parsed set. The one
    exception is Maryland 529, so that name is kept whole.

    Everything after the agency is the county, and where the row prints no
    county at all - the task-order tables print Agency, sub-number, Vendor and
    nothing else - the parent item's county is used. The parent's, not the
    line's: reading the county off the line puts the sub-number and the first
    word of the vendor name in it ("1.3 Oakland").
    """
    texts = [w["text"] for w in left_words]
    if not texts:
        return {"agency": parent_agency, "county": parent_county}
    take = 2 if texts[0] == "Maryland" and len(texts) > 1 else 1
    agency = " ".join(texts[:take])
    county = " ".join(texts[take:]).strip()
    return {"agency": agency, "county": county or parent_county}


def split_columns(words, bounds):
    """One line of words -> (item, agency, county, vendor, description)."""
    b1, b2, b3, b4 = bounds
    cols = [[], [], [], [], []]
    for w in words:
        x = w["x0"]
        i = 0 if x < b1 else 1 if x < b2 else 2 if x < b3 else 3 if x < b4 else 4
        cols[i].append(w["text"])
    return tuple(" ".join(c).strip() for c in cols)


def blank(item):
    return {
        "meeting_date": None, "agenda": None, "doc_number": None,
        "parent_item": None, "multi_vendor": 0, "action_note": "",
        "item_type": None, "agency": "", "county": "", "vendor_raw": "",
        "description": "", "amount_usd": None, "amount_basis": None,
        "term_start": None, "term_end": None, "action": None,
        "discussion": None, "references_doc": None, "contract_id": None,
        "source_pdf": None, "source_page": None, "raw_text": "",
        "is_it": 0, **item,
    }


def parse_amount(text):
    """(amount in dollars, basis) from an item's description text.

    Prefers "Total Amount:" over "Amount:" when both are present, because an
    item that lists a retroactive part and a proactive part prints both and the
    total is the one the Board approved. Returns (None, 'no change') for a
    modification that changes term only, and marks revenue items so they are
    never added to spend.
    """
    best = None
    parts = []
    for m in AMOUNT_LABEL.finditer(text):
        label = m.group("label").lower()
        tail = m.group("tail")
        rank = 3 if label.startswith("total") else 2 if label == "amount" else 1
        if "no change" in tail.lower():
            cand = (rank, None, "no change", label)
        else:
            money = MONEY.search(tail)
            if not money:
                continue
            value = float(money.group(1).replace(",", ""))
            # "Amount:$10 million" - the figure is written out rather than
            # printed in full, and read literally it is off by a factor of a
            # million.
            unit = tail[money.end():money.end() + 12].lower()
            if unit.lstrip().startswith("million"):
                value *= 1e6
            elif unit.lstrip().startswith("billion"):
                value *= 1e9
            # A figure the Board gives back rather than adds. The summaries
            # print it three ways - "Reduction Amount: ($667,045)",
            # "Amount: -$5,735,654. (decrease)" and a bare parenthesised
            # figure - and all three mean the same thing.
            before = text[max(0, m.start() - 24):m.start()].lower()
            lead = tail[:money.start()].rstrip()
            if (lead.endswith("-") or lead.endswith("(")
                    or tail.lstrip().startswith("(")
                    or "reduc" in before or "decrease" in tail.lower()):
                value = -value
            # "NTE" is printed before the label as often as after it
            # ("NTE Amount: $2,894,688"), so both sides are checked.
            scope = (before + " " + tail).lower()
            if "nte" in scope or "not to exceed" in scope:
                basis = "not-to-exceed"
            elif "estimated" in scope:
                basis = "estimated"
            else:
                basis = "fixed"
            if "revenue" in label:
                basis = "revenue-to-state"
            cand = (rank, value, basis, label)
        if cand[1] is not None and PART_LABEL.search(before):
            parts.append(cand[1])
        if best is None or cand[0] > best[0]:
            best = cand
    # An item that ratifies past spending AND authorises future spending prints
    # the two halves separately and no total: "Retroactive Amount: $750,043.
    # Extension Amount: $1,665,489." The Board approved both, so both are
    # counted. Only these three words trigger it - a bare second "Amount:" is
    # far more often a restatement than a second half, and adding those would
    # double-count.
    if best is not None and best[0] < 3 and len(parts) >= 2:
        best = (best[0], sum(parts), best[2], "sum of parts")
    if best is None:
        # Some items print "NTE $390,000" with no "Amount:" label at all.
        loose = re.search(r"(?:NTE|Not to Exceed)\s*\$\s?([0-9][0-9,]*)", text, re.I)
        if loose:
            return float(loose.group(1).replace(",", "")), "not-to-exceed"
        return None, None
    return best[1], best[2]


def classify(item_no, description):
    n = (item_no or "").upper()
    if "MOD" in n:
        return "modification"
    if "OPT" in n:
        return "renewal"
    if re.search(r"\bconfirm", description, re.I):
        return "confirmation"
    return "award"


def parse_pdf(path, meeting_date=None):
    name = os.path.basename(path)
    items = []
    agenda = None
    current = None
    sub_current = None

    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            lines = merge_split_action_lines(lines_of(page))
            bounds = page_bounds(lines, words)
            for words in lines:
                words_line = words
                whole = " ".join(w["text"] for w in words).strip()
                if all(h in whole for h in HEADER_WORDS) or PAGE_BANNER.match(whole):
                    continue
                if PAGE_FOOTER.search(whole) and len(whole) < 30:
                    continue
                item_col, agency, county, vendor, desc = split_columns(words, bounds)

                action = ACTION_LINE.match(whole)
                if action:
                    target = current
                    if target is None and items and items[-1]["action"] is None:
                        # the action line fell past a page break
                        target = items[-1]
                    if target is not None:
                        target["action"] = complete_action(
                            action.group("action").strip(),
                            action.group("note") or "")
                        target["discussion"] = action.group("discussion").strip()
                        target["contract_id"] = (action.group("doc") or "").strip() or None
                        target["action_note"] = (action.group("note") or "").strip()
                    current = None
                    continue

                if item_col == "" and agency == "" and county == "":
                    m = AGENDA_LINE.match(whole)
                    if m and not vendor and len(whole) < 80:
                        agenda = m.group("name").strip()
                        continue
                if whole.startswith("Agenda"):
                    m = AGENDA_LINE.match(whole)
                    if m:
                        agenda = m.group("name").strip()
                        continue

                sub = sub_x = None
                for w in words_line:
                    if SUB_NO.match(w["text"]) and bounds[1] <= w["x0"] < bounds[2]:
                        sub, sub_x = w["text"], w["x0"]
                        break
                if sub and current is not None:
                    money_tokens = [w for w in words_line
                                    if MONEY.match(w["text"]) and w["x0"] > bounds[3] + 115]
                    record = blank({
                        "meeting_date": meeting_date, "agenda": agenda,
                        "doc_number": "%s %s" % (current["doc_number"], sub),
                        "parent_item": current["doc_number"],
                        # The sub-item's own agency and vendor sit slightly
                        # left of the columns the parent item uses, so they are
                        # taken relative to the sub-number rather than to the
                        # page's column boundaries. See split_sub_agency for
                        # why the left-hand block is cut at the first word.
                        **split_sub_agency(
                            [w for w in words_line if w["x0"] < sub_x
                             and w["text"] != "REV"],
                            bounds, current["agency"], current["county"]),
                        "vendor_raw": " ".join(
                            w["text"] for w in words_line
                            if sub_x < w["x0"] < bounds[3]
                            and not DOC_TOKEN.match(w["text"])
                            and not SUB_NO.match(w["text"])).strip(),
                        "description": " ".join(
                            w["text"] for w in words_line
                            if bounds[3] <= w["x0"]
                            and w not in money_tokens).strip(),
                        "source_pdf": name, "source_page": page_no,
                        "raw_text": whole,
                        "action": current["action"],
                        "discussion": current["discussion"],
                    })
                    doc = [w["text"] for w in words_line
                           if DOC_TOKEN.match(w["text"])
                           and sub_x < w["x0"] < bounds[3]]
                    record["contract_id"] = doc[0] if doc else None
                    if money_tokens:
                        record["amount_usd"] = float(
                            money_tokens[-1]["text"].lstrip("$").replace(",", ""))
                        record["amount_basis"] = "fixed"
                    items.append(record)
                    sub_current = record
                    sub_current_x = sub_x
                    continue

                if sub_current is not None and SUB_NO_VENDOR.search(whole):
                    # another vendor sharing the sub-item above it
                    extra = " ".join(w["text"] for w in words_line
                                     if not SUB_NO_VENDOR.match(w["text"]))
                    sub_current["vendor_raw"] = (
                        sub_current["vendor_raw"] + "; " + extra).strip("; ")
                    sub_current["raw_text"] += "\n" + whole
                    continue

                if item_col and ITEM_NO.match(item_col):
                    current = blank({
                        "meeting_date": meeting_date, "agenda": agenda,
                        "doc_number": item_col, "agency": agency,
                        "county": county, "vendor_raw": vendor,
                        "description": desc, "source_pdf": name,
                        "source_page": page_no, "raw_text": whole,
                    })
                    items.append(current)
                    sub_current = None
                elif sub_current is not None and not item_col and not agency:
                    # A sub-item's vendor column starts at its own sub-number,
                    # which is well left of the page's vendor boundary. Its
                    # continuation line has no sub-number to measure from, so
                    # splitting it on the page's columns drops the second half
                    # of every wrapped vendor name into the county column:
                    # "Skyline Technology" + "Solutions, LLC" came out as
                    # "Skyline Technology LLC".
                    sub_vendor, sub_desc = vendor, desc
                    if sub_current_x is not None:
                        sub_vendor = " ".join(
                            w["text"] for w in words_line
                            if sub_current_x - 6 <= w["x0"] < bounds[3]
                            and not DOC_TOKEN.match(w["text"])).strip()
                        sub_desc = " ".join(w["text"] for w in words_line
                                            if w["x0"] >= bounds[3]).strip()
                    if sub_vendor:
                        sub_current["vendor_raw"] = (
                            sub_current["vendor_raw"] + " " + sub_vendor).strip()
                    if sub_desc:
                        sub_current["description"] = (
                            sub_current["description"] + " " + sub_desc).strip()
                    sub_current["raw_text"] += "\n" + whole
                elif current is not None:
                    # Agency and county are printed once, on the item's first
                    # line. Accumulating them across continuation lines turned
                    # an item that adds 113 master contractors into an agency
                    # field holding 113 company names.
                    if vendor:
                        current["vendor_raw"] = (current["vendor_raw"] + " " + vendor).strip()
                    if desc:
                        current["description"] = (current["description"] + " " + desc).strip()
                    current["raw_text"] += "\n" + whole

    # A sub-item takes its parent's Board action. The action line is printed
    # after the whole item, sub-items included, so at the moment a sub-item is
    # built the parent does not have one yet.
    by_number = {}
    for it in items:
        if not it["parent_item"]:
            by_number[(it["source_pdf"], it["doc_number"])] = it
    for it in items:
        if it["parent_item"]:
            parent = by_number.get((it["source_pdf"], it["parent_item"]))
            if parent is not None:
                it["action"] = parent["action"]
                it["discussion"] = parent["discussion"]
                it["action_note"] = parent["action_note"]
                # "Sub-Item 5.1 was withdrawn at the meeting" withdraws exactly
                # that task order and nothing else on the item.
                withdrawn = {m.group(1) for m
                             in WITHDRAWN_SUB.finditer(parent["action_note"] or "")}
                if it["doc_number"].split(" ")[-1] in withdrawn:
                    it["action"] = "Withdrawn"
                it["agenda"] = it["agenda"] or parent["agenda"]

    for it in items:
        text = it["description"]
        if it["amount_usd"] is None:
            it["amount_usd"], it["amount_basis"] = parse_amount(text)
        # An item that ratifies past spending and authorises future spending
        # prints two terms - "Retroactive Term: 9/23/21 - 10/6/21; Proactive
        # Term: 10/7/21 - 6/30/22" - and the Board approved the whole span.
        # Taking the first match alone records only the retroactive half, which
        # made a five-year award look like a two-week one.
        terms = list(TERM.finditer(text))
        if terms:
            it["term_start"] = normalise_date(terms[0].group("start"))
            last = terms[-1] if re.search(r"roactive", text, re.I) else terms[0]
            it["term_end"] = normalise_date(last.group("end"))
        refs = [g for m in REFERENCE.finditer(text) for g in m.groups() if g]
        it["references_doc"] = "; ".join(dict.fromkeys(refs)) or None
        it["item_type"] = classify(it["doc_number"], text)
        it["is_it"] = int(bool(IT_ITEM_NO.search(it["doc_number"] or ""))
                          or bool(IT_AGENDA.search(it["agenda"] or "")))
        # Some items are a table of sub-items - "add 113 master contractors",
        # or four task orders to four different companies under one approval.
        # The money on those is real but it does not belong to one vendor, so
        # they are flagged here and left out of vendor rankings later.
        it["multi_vendor"] = int(
            bool(re.search(r"Sub\s*Item|\b1\.1\b|master contractors",
                           it["raw_text"], re.I))
            or len(it["vendor_raw"]) > 120)
    return items


def normalise_date(s):
    m, d, y = s.split("/")
    y = int(y)
    if y < 100:
        y += 2000 if y < 70 else 1900
    return "%04d-%02d-%02d" % (y, int(m), int(d))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", default="data/raw/summaries")
    ap.add_argument("--manifest", default="data/raw/manifest.csv")
    ap.add_argument("--out", default="data/interim/items_all.csv")
    args = ap.parse_args()

    dates = {}
    if os.path.exists(args.manifest):
        with open(args.manifest, newline="") as fh:
            for row in csv.DictReader(fh):
                dates[row["filename"]] = row["meeting_date"] or None

    paths = sorted(glob.glob(os.path.join(args.pdfs, "*.pdf")))
    rows, per_file = [], []
    for path in paths:
        name = os.path.basename(path)
        items = parse_pdf(path, dates.get(name))
        rows.extend(items)
        per_file.append((name, len(items), sum(i["is_it"] for i in items),
                         sum(1 for i in items if i["action"] is None)))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    cols = ["meeting_date", "agenda", "doc_number", "item_type", "agency",
            "county", "vendor_raw", "description", "amount_usd",
            "amount_basis", "term_start", "term_end", "action", "discussion",
            "references_doc", "contract_id", "is_it", "multi_vendor",
            "parent_item", "action_note", "source_pdf",
            "source_page", "raw_text"]
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    it_rows = [r for r in rows if r["is_it"]]
    print("%d files, %d items, %d IT items" % (len(paths), len(rows), len(it_rows)))
    noaction = sum(1 for r in rows if r["action"] is None)
    print("items with no action line: %d (%.2f%%)"
          % (noaction, 100.0 * noaction / max(len(rows), 1)))
    empty = [p for p in per_file if p[2] == 0]
    if empty:
        print("meetings with ZERO IT items - open these by hand:")
        for name, n, nit, na in empty:
            print("   %-34s %3d items" % (name, n))


if __name__ == "__main__":
    main()
