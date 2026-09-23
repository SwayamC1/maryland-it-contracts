"""
Vendor name resolution.

"Carbonado Technologies, Inc.", "Carbonado Technologies Inc" and "Carbonado
Tech" are one company and three strings. Normalising case, punctuation and
corporate suffixes collapses most of it; the rest needs fuzzy matching.

The important part is what happens after the fuzzy match. Automated matching
will cheerfully merge two genuinely different companies that happen to be named
alike - "Maryland Health Systems" and "Maryland Health Solutions" score 92 - so
every proposed merge above the threshold is written to
data/interim/vendor_merges.csv for review, and only merges marked keep=1 are
applied. The review file is committed, so anyone can see which calls were made
and disagree with them.
"""

import csv
import os
import re

from rapidfuzz import fuzz, process

# Legal-form suffixes only. An earlier version also stripped words like
# "group", "software", "international" and "usa", which are part of real
# company names: it turned SHI International Corp. into "shi", Colossus d/b/a
# Interact Public Safety Systems into something unreadable, and collapsed two
# unrelated firms into a vendor called "software".
SUFFIXES = [
    "incorporated", "inc", "llc", "l l c", "llp", "l l p", "lp", "plc", "pllc",
    "corporation", "corp", "company", "co", "ltd", "limited", "pc", "pa",
    "holdings", "the",
]
SUFFIX_RE = re.compile(r"\b(?:%s)\b" % "|".join(SUFFIXES))
AMPERSAND = re.compile(r"\s*&\s*")
NONWORD = re.compile(r"[^a-z0-9 ]+")
SPACES = re.compile(r"\s+")

# Placeholders the summaries print where a vendor would go.
NOT_A_VENDOR = {"", "..", "--", "various", "n a", "na", "tbd", "to be determined"}

# A state document number that landed in the vendor column, e.g.
# "CAS Severn E00P460090". It identifies the contract, not the company.
DOC_IN_NAME = re.compile(r"\b(?:CO[A-Z]\w{3,}|[0-9A-Z]{3}[A-Z]?\d{6,}\w*)\b")

# Description text that leaked into the vendor column. These items are real
# approvals; they just do not name one company, so they keep their money and
# lose their vendor attribution.
DESCRIPTION_WORDS = {"purchase", "orders", "order", "contracts", "approved",
                     "master", "task", "under", "previously", "information"}


def looks_like_description(name):
    """True when the vendor column holds description text, not a company."""
    words = set((name or "").lower().replace(",", " ").split())
    return len(words & DESCRIPTION_WORDS) >= 3 or len(name or "") > 70


def normalise(name):
    """'Carbonado Technologies, Inc.' -> 'carbonado technologies'."""
    s = DOC_IN_NAME.sub(" ", name or "")
    s = s.lower()
    s = AMPERSAND.sub(" and ", s)
    s = s.replace("t/a", " ")
    s = NONWORD.sub(" ", s)
    s = SPACES.sub(" ", s).strip()
    s = SUFFIX_RE.sub(" ", s)
    return SPACES.sub(" ", s).strip()


def propose_merges(names, threshold=92):
    """Candidate merges between distinct normalised names.

    Returns rows of (keep, canonical, alias, score) with keep left at 1 for a
    reviewer to change. Blocking on the first token keeps this from being an
    O(n^2) comparison across several thousand vendors and, more usefully, stops
    it proposing merges between companies whose names do not even start alike.
    """
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    unique = sorted(counts, key=lambda n: (-counts[n], n))

    blocks = {}
    for n in unique:
        blocks.setdefault(n.split(" ")[0][:6], []).append(n)

    proposals, merged = [], set()
    for members in blocks.values():
        if len(members) < 2:
            continue
        canon_order = sorted(members, key=lambda n: (-counts[n], len(n)))
        for canonical in canon_order:
            if canonical in merged:
                continue
            others = [m for m in members if m != canonical and m not in merged]
            if not others:
                continue
            for alias, score, _ in process.extract(
                    canonical, others, scorer=fuzz.token_sort_ratio,
                    limit=len(others), score_cutoff=threshold):
                merged.add(alias)
                proposals.append({"keep": 1, "canonical": canonical,
                                  "alias": alias, "score": round(score, 1),
                                  "canonical_items": counts[canonical],
                                  "alias_items": counts[alias]})
    return proposals


def load_decisions(path):
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("keep", "1")).strip() in ("1", "true", "True"):
                out[row["alias"]] = row["canonical"]
    return out


def apply_decisions(name, decisions):
    key = normalise(name)
    if key in NOT_A_VENDOR:
        return None
    seen = set()
    while key in decisions and key not in seen:
        seen.add(key)
        key = decisions[key]
    return key or None
