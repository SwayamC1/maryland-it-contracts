# What Maryland actually pays for IT

**A structured dataset of every Maryland IT contract the Board of Public Works
approved between January 2016 and September 2026 — built from the state's own
PDF meeting summaries, seven years further back than any structured version of
this record has gone before.**

Maryland's Board of Public Works approves every state IT contract and every
later modification to it. The record is public, and has been for decades, as
PDF meeting summaries. The Comptroller's *structured* version — the one you can
sort, filter and download — begins on **7 December 2022**.

This repository extends it back to **January 2016**: 231 meeting summaries,
22,786 agenda items, **2,154 approved IT items worth $5.91B in approved value**,
every row carrying the PDF and page number it came from.

- **[The findings](docs/findings.md)** — six questions, each with a prediction
  written down before it was run
- **[The dataset](data/final/md_it_contracts.csv)** — one row per approved IT
  item
- **[What was excluded, and why](data/final/md_it_dropped_items.csv)** — all 344
  of them, each with a written reason
- **[The explorer](app/streamlit_app.py)** — search by vendor, agency or
  contract; every row links to the source PDF
- **[Methodology](docs/methodology.md)** · **[Data
  dictionary](docs/data-dictionary.md)** · **[Source
  notes](docs/source-notes.md)** · **[Build log](docs/log.md)**

---

## The one thing to understand before reading any number

**The Board approves ceilings, not expenditures.**

An item reading "Not to Exceed $390,000" means the state *may* spend up to that
amount, not that it did. Everything measured here is **approved contract
value**. Every column name, chart title and sentence in this repository says so,
and `amount_basis` records for every row whether the figure was a
not-to-exceed ceiling, a fixed price, an estimate, or revenue owed **to** the
state rather than paid by it.

Two things follow from that:

**Growth is not waste.** Contracts grow for scope changes, term extensions,
federal requirements and emergencies. This project reports how far approved
value moves after award and lists the explanations. It does not pick one.

**No wrongdoing is named.** Vendors and agencies appear here as data. Outliers
are shown as outliers, next to a link to the state's own page, and the reader
draws the conclusion. I am not an auditor and this is not an audit.

---

## How accurate is it

Two numbers, measured two different ways. Both are published in full, including
the parts that are not flattering.

### Against the Comptroller's own dataset (Dec 2022 onward)

The Comptroller publishes structured BPW data from December 2022. This pipeline
processed the same meetings, so the overlap is a benchmark with a real answer
key.

| Measure | Value | |
|---|---|---|
| **Recall** | **73.1%** | 837 of their 1,145 IT rows found |
| Recall, on meetings whose summary records Board actions | 78.1% | 837 of 1,072 |
| **Precision** | **84.0%** | 837 of my 997 matched IT items |
| Meeting date agreement | 100.0% | |
| Amount agreement | 98.5% | |
| Vendor agreement | 97.0% | |
| Contract number agreement | 51.0% | see below |

Every unmatched row on either side is written out to be opened by hand:
`validation_misses.csv`, `validation_extras.csv`,
`validation_disagreements.csv`.

Contract-number agreement is low for a structural reason, not a bug — it is
described under "The finding I did not want" below.

### Against the source PDFs (2016–2022, where no answer key exists)

A sample of 100 items, read by hand against the printed page, field by field.

| Field | Correct |
|---|---|
| meeting date | 100% |
| agency | 100% |
| county | 100% |
| amount | 98% |
| item type | 98% |
| Board action | 98% |
| term | 95% |
| vendor name | 89% |
| **overall** | **97.25%** — 22 errors in 800 field checks |

81 of the 100 items were correct in all eight fields. The worksheet, with a
written note on every single error, is
[`hand_audit_holdout.csv`](data/final/hand_audit_holdout.csv).

**Why that sample and not the other one.** I ran this audit twice. The first
sample of 100 found nine classes of parser bug. I fixed them — and that made the
first sample's score worthless, because the parser had then been tuned on the
very items being scored. It came out at 99.1%. A second sample, drawn with a
different seed and not looked at until the parser was frozen, came out at
**97.25%**. The 1.9-point gap between them is the size of the lie I would have
told by publishing the first number. Both worksheets are in `data/final/` so you
can check either.

The errors the held-out sample found were fixed afterwards too, so 97.25% is a
**lower bound** on the dataset as it now stands. It is deliberately not adjusted
upwards — that would be the same circularity all over again.

---

## The finding I did not want

The project was built to answer one question: **how much does a Maryland IT
contract grow after it is approved?** The honest answer is that these documents
cannot fully answer it, and *why* they cannot is the most useful thing here.

**Maryland uses two identifier systems in the same column.** An award carries a
procurement contract number — `F50B2600034`. A modification usually carries a
**change-order control number** — `COL26444` — which appears nowhere else in the
Summary: not on the award it changes, not on any other item.

In this dataset:

- 825 awards carry a document number; **17 of them (2%)** use a control number.
- 544 modifications and renewals carry one; **342 of them (63%)** use a control
  number.

For roughly two thirds of modifications, **the published Summary does not say
which contract is being modified.** The Comptroller's dataset occasionally
prints both numbers in one field separated by " / ", and a crosswalk built from
those resolves a handful. The rest cannot be joined from these two public
sources at all.

So the growth analysis runs on the 366 contracts that *can* be linked, the count
is printed next to every growth figure, and the headline of this repository is
the dataset rather than a growth rate. Among those 366: median growth **0.0%**,
**5% modified at all**, and a median of **+100%** among the ones that moved —
most contracts never change, and the ones that do tend to double.
[Full detail, distribution and caveats.](docs/findings.md#q3-q4--how-far-a-contract-moves-after-it-is-approved)

---

## What is in here

```
data/raw/manifest.csv      all 231 Summary PDFs: URL, bytes and SHA-256 of each
data/raw/                  the Comptroller's export, untouched
data/final/                the published dataset, the drops, the validation output, the audits
src/                       the pipeline, one script per step
app/streamlit_app.py       the explorer
notebooks/01_collect.ipynb collection, as a Colab notebook
figures/                   six figures, light and dark
docs/                      findings, methodology, data dictionary, source notes, build log
```

### The pipeline

```
src/collect.py            read the year index pages, download 231 Summary PDFs
src/parse_summaries.py    PDF -> one row per agenda item, by word position
src/build_dataset.py      classify IT, resolve vendors, drop and record
src/validate.py           benchmark against the Comptroller's dataset
src/link_contracts.py     link modifications to awards, roll up by contract
src/analyse.py            the six questions
src/make_figures.py       the six figures
src/hand_audit.py         draw the audit sample and pull each item's printed text
```

Each step runs on its own and each one writes down what it dropped and why.

```bash
pip install -r requirements.txt
python src/run_all.py
```

**Nothing is edited by hand at any point.** The 231 source PDFs are not
committed - 43MB of documents the state already publishes - but
[`data/raw/manifest.csv`](data/raw/manifest.csv) carries the URL, byte count and
**SHA-256 of every one of them**, so a re-collection can be verified as
byte-identical to the one these numbers were built from:

```bash
python src/collect.py          # or notebooks/01_collect.ipynb in Google Colab
sha256sum -c <(awk -F, 'NR>1 {print $7"  data/raw/summaries/"$4}' data/raw/manifest.csv)
```

The Comptroller's export, which is the benchmark rather than an input, is
committed unmodified.

---

## No model is used anywhere in this pipeline

Not for extraction, not for classification, not for vendor matching.

That was not the plan. The plan assumed the summaries were ruled tables, that
`extract_table()` would carry most of the work, and that a language model would
handle the rows it could not. The first assumption turned out to be false —
`extract_table()` returns **zero rows** on every summary, because these are
unruled positioned text — and once the parser was reading word coordinates
instead, the third assumption was unnecessary.

This is not a boast about avoiding AI. It is a statement about what can be
checked: every field in the published dataset comes from a rule you can read in
`src/`, and every row carries the PDF and page it came from.

Two judgement calls are made by a human rather than a rule, and both are
committed so you can disagree with them:

- **Vendor merges.** Names are normalised and fuzzy-matched, and then every
  proposed merge is reviewed by hand in
  [`data/interim/vendor_merges.csv`](data/interim/vendor_merges.csv), which
  carries a `keep` column and a note. Two proposed merges were rejected —
  "Advance" and "Advanced Management Services" may be two different firms, and
  the documents give no way to tell.
- **Which items count as IT.** Three signals, any one of which is enough; the
  rule is in `src/build_dataset.py` and the borderline cases are in the drop
  file.

---

## Known limits

Written here rather than buried, because a dataset whose limits you have to
discover yourself is worse than no dataset.

- **Two thirds of modifications cannot be linked to their contract.** See above.
  This is the big one.
- **Vendor names are the weakest field, at 89%.** Names wrap across lines in a
  narrow column and a wrapped name can lose its last word. `vendor_raw` is
  published next to `vendor_clean` so you can always see what the page printed.
- **About 5% of items have no Board action recorded.** Those summaries were
  posted before the meeting and never updated afterwards. The items stay in the
  dataset with `action` empty and are excluded from every approved-value figure.
- **An item with a Part A and a Part B and no printed total** is recorded at the
  value of Part A. Where the halves are labelled Retroactive/Proactive or
  Extension they are added; where they are labelled "PART A" and "PART B" they
  are not, because a bare second "Amount:" is more often a restatement than a
  second half.
- **A handful of "record correction" items** reprint the whole procurement
  summary box down the middle of the page, and those lines land in the vendor
  column. They are visible immediately in the CSV — their `vendor_raw` contains
  the words "Procurement Method".
- **Task orders bundled inside an item only appear from about 2020**, because
  that is when the summaries started printing them as numbered sub-items. Q1
  reports them as a separate column for this reason; adding the columns would
  invent a step change that is a change in document format.
- **2026 is a partial year**, through 16 September.

---

## Sources

- **Board of Public Works meeting Summaries**,
  [bpw.maryland.gov](https://bpw.maryland.gov/Pages/meetingDocuments_year.aspx) —
  231 PDFs, collected 16 September 2026. Every one is listed in
  `data/raw/manifest.csv` with its URL, size and SHA-256.
- **Comptroller of Maryland BPW Dashboard export**,
  [interactive.marylandcomptroller.gov/BPWDashboard](https://interactive.marylandcomptroller.gov/BPWDashboard) —
  15,242 rows, December 2022 to August 2026, committed unmodified. Used only as
  a benchmark, never as an input to the dataset.

The Comptroller's dashboard carries a disclaimer that is also the argument for
this project existing: the meeting documents "take precedence over any
information presented in the dashboard in the event of a discrepancy".

## Corrections

If you find an error, open an issue with the `source_pdf` and `source_page` from
the row — every row in the dataset carries both, which is the whole point. I
would rather be corrected than be quoted.

## Licence

Code: MIT. Data: the underlying documents are Maryland public records; the
derived dataset is released under CC0.
