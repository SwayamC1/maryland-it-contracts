# Methodology

## The question

Maryland's Board of Public Works approves every state IT contract and every
later modification to it. The record is published as PDF meeting summaries
going back decades. The Comptroller's structured dataset of that record starts
in December 2022.

So: extend the structured record backwards, link each modification to the award
it changes, and answer a question nobody has answered publicly. **How much does
a Maryland IT contract grow after it is approved?**

## The caveat the whole project rests on

The Board approves **ceilings, not expenditures**. An item reading "Not to
Exceed $390,000" means the state may spend up to that amount, not that it did.
Everything measured here is *approved contract value*. Every column name, chart
title and sentence says so, and `amount_basis` records for every row whether
the figure was a not-to-exceed ceiling, a fixed price, an estimate, or a
revenue figure owed **to** the state rather than paid by it.

A second caveat follows from the first: **growth is not waste**. Contracts grow
for scope changes, term extensions, federal requirements and emergencies. This
project reports how far approved value moves after award and lists the
explanations. It does not pick one, and it names no wrongdoing. If a contract
is an outlier, it is shown as an outlier next to a link to the state's own
page, and the reader draws the conclusion.

## Window

Calendar 2016 through 16 September 2026, chosen after checking that the item
table is laid out the same way at both ends. 231 meeting summaries.

## Pipeline

```
notebooks/01_collect.ipynb   read year index pages, download 231 Summary PDFs
src/parse_summaries.py       PDF -> one row per agenda item, by word position
src/build_dataset.py         classify IT, resolve vendors, drop and record
src/validate.py              benchmark against the Comptroller's dataset
src/link_contracts.py        link modifications to awards, roll up by contract
src/analyse.py               the six questions
src/make_figures.py          the six figures
app/streamlit_app.py         the explorer
```

Every step is a script that can be run on its own, and each writes what it
dropped and why.

### Extraction is deterministic

The plan this was built from assumed the summaries were ruled tables, that
`extract_table()` would carry roughly 80% of rows, and that a language model
would handle the rest. The first assumption turned out to be false -
`extract_table()` returns **zero** rows on every summary tried - and once the
parser was reading word coordinates instead, the third was unnecessary.

**No model is used anywhere in this pipeline.** Not for extraction, not for
classification, not for vendor matching. That is not a boast about avoiding AI;
it is a statement about what can be checked. Every field in the published
dataset comes from a rule that can be read in `src/`, and every row carries the
PDF and page it came from.

### The fields

| Field | Where it comes from |
|---|---|
| `meeting_date` | the Summary's filename, via the collection manifest |
| `agenda` | the `Agenda:` section heading above the item |
| `doc_number` | the Item column, e.g. `17-IT`, `3-IT-MOD` |
| `item_type` | award / modification / renewal / confirmation, from the item number suffix and the description |
| `agency`, `county` | the Agency and County columns of the item's first line |
| `vendor_raw` | the Vendor column, accumulated across the item's lines |
| `vendor_clean` | normalised and merged, see below |
| `description` | the Description column, accumulated |
| `amount_usd`, `amount_basis` | the last `Amount:` / `Total Amount:` label in the description; `Total Amount` wins when both are present |
| `term_start`, `term_end` | `Term: 4/20/26 - 4/19/28` |
| `action`, `discussion` | the `action:` line closing the item |
| `contract_id` | `Doc. No.` on that same line |
| `references_doc` | cross references pulled from the description text |
| `multi_vendor` | set when one item covers several companies |
| `source_pdf`, `source_page` | so any row can be checked in under a minute |

Anything not clearly stated in the document is left empty. Empty never means
zero.

## What gets dropped, and why

Recorded row by row in `data/final/md_it_dropped_items.csv`:

- **No action recorded.** About 5% of items sit in summaries that were posted
  before the meeting and never updated afterwards. There is no Board action to
  read, so they cannot be counted as approved.
- **Action was not "Approved".** Deferred and withdrawn items are not money.
- **Revenue to the state.** A handful of IT items are agreements under which
  the state is paid. Counting those as spend would be backwards.
- **No dollar figure**, including modifications that change only the term
  ("Amount: No change"). Those still appear in the dataset; they just cannot
  contribute to a total.

And at the contract level, in `data/final/md_it_rollup_dropped.csv`:

- **No original award inside the window.** A contract whose award was approved
  in 2014 and whose modifications land in 2019 looks like infinite growth.
- **Awarded after the cutoff.** The growth analysis is cut at awards made
  through 2022, so every contract in it has had at least three years in which
  it could have been modified.
- **Multi-vendor items.** One approval covering four task orders to four
  companies is real money but it is not one contract's.

## Vendor resolution

Normalise case, punctuation and corporate suffixes; fuzzy match the remainder
with `rapidfuzz`, blocked on the first token; then **review every proposed
merge by hand** in `data/interim/vendor_merges.csv`, which is committed with a
`keep` column. Only merges marked `keep=1` are applied. Automated matching will
cheerfully merge two different companies with similar names, and a procurement
person spots that instantly.

## Validation

Two numbers, both in the README.

**The benchmark.** The Comptroller publishes structured data from December 2022
onward, and this pipeline processed the same meetings. Matching runs in three
passes, strongest key first: meeting date plus item number, then meeting date
plus a shared contract number, then meeting date plus vendor and amount. Recall,
precision and per-field agreement are reported separately, because a pipeline
that is perfect on dates and shaky on amounts is a different animal from the
reverse. Every unmatched row on either side is written out to be opened by hand.

**The hand audit.** A sample of items from the **pre-2022** years, where no
answer key exists, checked field by field against the source PDFs, with the
worksheet published. `src/hand_audit.py` draws the sample and pulls the text
printed around each sampled item so the reading is done against the document.

The audit was run twice on two independent samples, and only the second number
is published. The first sample found nine classes of parser bug; fixing them
made that sample's score meaningless, because the parser had been tuned on the
items being scored. The second sample was drawn with a different seed and not
looked at until the parser was frozen. Its errors were fixed afterwards too, so
the published figure is a lower bound on the dataset as it now stands - it is
deliberately not adjusted upwards, since that would reintroduce exactly the
circularity the second sample exists to avoid.

Sampling is by hash of each item's own identity rather than by position in the
file, so the same items stay in the sample when the dataset gains or loses a
row. Both worksheets are published.

## Linking a modification to its contract

This is the limit of what the Summaries can do, and it shapes what the growth
question can honestly claim.

Maryland uses **two identifier systems** in the same `Doc. No.` position. An
award carries a procurement contract number - `F50B2600034`. A modification
usually carries a **change-order control number** - `COL26444` - which appears
nowhere else in the Summary: not on the award it changes, not on any other
item. Grouping on `Doc. No.` therefore joins awards to awards and leaves most
modifications stranded in groups of one.

`src/link_contracts.py` does what can be done: it groups on `contract_id`, falls
back to cross references found in the description text, and builds a crosswalk
from the Comptroller's own Contract field, which occasionally prints both
numbers separated by " / ". That resolves a small number of them. The rest
cannot be linked from these two published sources at all.

The consequence is stated wherever a growth figure appears: the number of
contracts the analysis actually runs on is printed next to the result, and the
growth figures are a floor, not an estimate of the whole.

## Reproducing

```
pip install -r requirements.txt
python src/run_all.py
```

The raw PDFs are committed, so nothing is downloaded and nothing is edited by
hand at any point. To re-collect from the state's site instead, run
`notebooks/01_collect.ipynb` in Google Colab or `python src/collect.py` anywhere
with internet.
