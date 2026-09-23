# Findings

Everything below is **approved contract value** — a ceiling the Board of Public
Works authorised, not money Maryland spent. Every row behind every number
carries the PDF and page it came from, so any figure here can be checked
against the state's own document in about a minute.

Six questions were written down, with a prediction for each, before any of them
was run. The predictions are in [`log.md`](log.md). Three of the six came out
close to what I expected. Three did not, and those are the interesting ones.

---

## The dataset is the finding

Maryland's Board of Public Works approves every state IT contract and every
later modification to it. The record has been published as PDF meeting
summaries for decades. The Comptroller's *structured* version of that record —
the one you can sort, filter and download — starts on 7 December 2022.

This project pushes the structured record back to January 2016:

| | |
|---|---|
| Meeting summaries read | 231 |
| Agenda items parsed | 22,786 |
| IT items identified | 2,498 |
| IT items approved and counted | **2,154** |
| IT items excluded, each with a written reason | 344 |
| Years added ahead of the Comptroller's dataset | **almost seven** |
| Approved IT value in the window | **$5.91B across 591 named vendors** |

No language model is used anywhere in the pipeline. Not for extraction, not for
classification, not for vendor matching. Every field comes from a rule you can
read in `src/`, which is the only reason the accuracy numbers below mean
anything.

---

## Q1 — Approved IT value by year

**Prediction:** a rising line, steeper after 2020, with a COVID dip in 2020 and
a jump in 2021–22 for remote-work infrastructure.

**Result:** rising, yes. COVID dip, no — 2020 was the largest year to that
point, not the smallest.

| Year | Agenda items | Bundled task orders | Items |
|---|---|---|---|
| 2016 | $557.9M | — | 108 |
| 2017 | $803.3M | — | 90 |
| 2018 | $490.1M | — | 101 |
| 2019 | $557.2M | — | 90 |
| 2020 | $1.22B | $195.6M | 138 + 117 |
| 2021 | $1.46B | $583.7M | 121 + 112 |
| 2022 | $1.36B | $473.9M | 124 + 173 |
| 2023 | $1.40B | $352.7M | 131 + 175 |
| 2024 | $1.19B | $304.7M | 152 + 174 |
| 2025 | $2.53B | $214.3M | 128 + 111 |
| 2026 (to 16 Sept) | $958.9M | $22.3M | 88 + 21 |

Two columns, not one, and that is not fussiness. Until about 2020 an IT item
named one vendor. From 2020 the summaries increasingly print an item that says
"Approve ten Task Orders under previously-approved master contracts" followed
by a numbered table — each row its own agency, vendor and amount. Those rows
are real approvals and they are in the dataset, but they did not exist as
separate line items before 2020. Adding the two columns together would make
2019 and 2021 incomparable and invent a step change that is a **change in
document format**, not in spending.

Read the first column alone and the shape is: roughly $500–800M a year through
2019, then a step up to $1.2–1.5B from 2020 onward, then $2.53B in 2025.

**What I will not claim.** I do not know that Maryland's IT spending tripled.
I know that the value the Board *approved* tripled, that the Board approves
ceilings, and that a ceiling is not a payment.

---

## Q2 — Who holds the approvals

**Prediction:** heavy concentration, top 10 holding more than half; names would
be resellers and staffing firms rather than the software makers.

**Result:** half right. The second half held; the first did not.

The top 10 vendors hold **39.1%** of $5.91B — concentrated, but well short of
the "more than half" I predicted. The long tail is longer than I expected: 591
named vendors for a state of six million people.

| Vendor | Approved | Items |
|---|---|---|
| Scientific Games International, Inc. | $411.9M | 5 |
| SHI International Corp. | $347.3M | 37 |
| Amazon Web Services, Inc. | $241.4M | 1 |
| Deloitte Consulting LLP | $216.2M | 9 |
| Motorola Solutions, Inc. | $213.1M | 16 |
| TransCore LP | $195.1M | 5 |
| Carahsoft Technology Corporation | $191.6M | 54 |
| Digital Management, LLC | $182.0M | 6 |
| Strategic Communications | $168.0M | 2 |
| Revenue Solutions, Inc. | $145.1M | 5 |

The prediction about *kinds* of company held. SHI and Carahsoft are resellers —
between them 91 items — and the software vendors whose products the state
actually runs mostly do not appear, because the state buys their licences
through a master contract held by someone else. The single largest line in the
table, Amazon Web Services at $241.4M on **one item**, is the exception that
shows the rule: when the state does contract a platform directly, it does it
once and for a great deal of money.

A further 419 items name no single vendor at all — a master contract award, or
a table of task orders going to a dozen companies. Their money is real and it
is in the year totals, but it is flagged `multi_vendor` and kept out of this
table, because attributing it to one name would be wrong.

---

## Q3, Q4 — How far a contract moves after it is approved

This is the question the project was built to answer, and the honest answer is
**that it cannot be answered from these documents as well as I expected**.

Of 1,277 contracts assembled from linked items, **366** qualify for the growth
analysis: the original award falls inside the window, it carries a dollar
figure, it was awarded through 2022 so it has had at least three years in which
it could have been modified, and no item on it covers several vendors. Every
excluded contract is listed with its reason in
`md_it_rollup_dropped.csv`.

Among those 366:

| | |
|---|---|
| Median growth | **0.0%** |
| Contracts modified at all | **18 of 366 (5%)** |
| Median growth *among those that changed* | **100.0%** |

**Prediction:** median growth of 10–25%. **Result:** zero.

The distribution, not the median, is the finding:

| Growth from award to total approved | Contracts | Share |
|---|---|---|
| no change | 348 | 95.1% |
| under 10% | 2 | 0.5% |
| 25 to 50% | 3 | 0.8% |
| 50 to 100% | 6 | 1.6% |
| 100 to 300% | 5 | 1.4% |
| over 300% | 2 | 0.5% |

My Q4 prediction — a large "no change" group, a thin middle, a long right tail —
was right, and more extreme than I guessed. A Maryland IT contract that gets
modified at all tends to *double*. Most never get modified.

The largest movers, each checkable at its source page:

| Contract | Agency | Original | Total approved | Growth |
|---|---|---|---|---|
| Q00B8400001 | PS | $522,596 | $2,416,074 | +362% |
| F50B6400032 | DIT | $728,198 | $3,143,730 | +332% |
| R00B2600056 | EDUC | $1,157,001 | $3,903,199 | +237% |
| Q00B6400088 | PS | $520,000 | $1,492,400 | +187% |
| 060B0600016 | DIT | $9,000,000 | $20,250,000 | +125% |

**These are outliers, not accusations.** A contract grows for scope changes,
term extensions, emergencies and federal requirements, and nothing in these
documents distinguishes a well-managed expansion from a badly-scoped original.
The item numbers and pages are published so a reader who wants to know *why*
one of these grew can go and read the item.

### Why 5% is a floor and not a rate

The "5% were modified at all" figure is almost certainly too low, and the reason
is the most useful thing this project found.

**Maryland uses two identifier systems in the same column.** An award carries a
procurement contract number — `F50B2600034`. A modification usually carries a
**change-order control number** — `COL26444` — which appears nowhere else in
the Summary: not on the award it changes, not on any other item.

In the published dataset:

- 825 awards carry a document number; **17** of them (2%) use a control number.
- 544 modifications and renewals carry one; **342** of them (63%) use a control
  number.

So for roughly two thirds of modifications, **the Summary does not say which
contract is being modified**. The Comptroller's dataset occasionally prints both
numbers in one field separated by " / ", and a crosswalk built from those
resolves a handful. The rest cannot be joined from these two published sources
at all.

That is a transparency finding in its own right, and it is why this page does
not lead with a growth rate. The growth figures above describe the 366
contracts that can be linked. Presenting them as "how much Maryland IT contracts
grow" would be exactly the kind of number this project exists to avoid.

---

## Q5 — Time from award to first change

**Prediction:** a peak around 12–24 months, at the end of a first option year,
rather than a smooth decay.

**Result:** too few linked contracts to say. Only **11** contracts in the
analysis have both an award and a datable later change, and they are spread
across five years with no shape:

| Months after award | Contracts |
|---|---|
| 0–6 | 1 |
| 6–12 | 1 |
| 12–18 | 2 |
| 18–24 | 2 |
| 30–36 | 1 |
| 36–42 | 1 |
| 54–60 | 1 |
| 60+ | 2 |

Eleven observations is not a distribution. The chart is published because
leaving it out would hide how thin the linkable data is, and the caption says
so. This is the same two-identifier problem as Q3, seen from a different angle.

---

## Q6 — Growth by agency

**Prediction:** transportation and health agencies would show the most growth,
their systems being the largest and the most entangled with federal rules.

**Result:** not supported. Every agency with at least five linked contracts has
a median growth of **0.0%**, because in every agency the large majority of
contracts are never modified. What separates agencies is the *share* that move
at all:

| Agency | Contracts | Share modified |
|---|---|---|
| DBM | 6 | 16.7% |
| HMH | 7 | 14.3% |
| DIT | 50 | 14.0% |
| DOHR | 9 | 11.1% |
| MDH | 11 | 9.1% |
| EDUC | 19 | 5.3% |
| PS | 42 | 4.8% |
| DOT | 93 | 3.2% |
| COMP, DGS, HCD, MSP, MPT, MDL, DJS, ELECTLAW | 5–30 each | 0.0% |

Transportation — the agency with the most linked contracts by a wide margin —
has the *lowest* modification rate of any agency with a meaningful count. My
prediction had it near the top.

With 6 to 93 contracts per agency, and the linking problem above sitting under
all of it, I would not put weight on the ordering. The honest reading is that
the Department of Information Technology and the budget and human-services
agencies revisit their contracts more often than transportation does, and that
a bigger sample would be needed to say more.

---

## By agency, by approved value

For completeness, because it is the table people usually want first:

| Agency | Approved | Items |
|---|---|---|
| DIT (Information Technology) | $5.44B | 437 |
| DGS (General Services) | $2.66B | 156 |
| VARIOUS (multi-agency items) | $1.45B | 43 |
| DOT (Transportation) | $1.33B | 423 |
| DOHR (Human Services) | $594.5M | 123 |
| MDH (Health) | $557.3M | 132 |
| LOTT (Lottery and Gaming) | $439.3M | 8 |

DIT's share reflects how Maryland buys: the Department of Information
Technology holds the statewide master contracts, so hardware and licensing for
other agencies is often approved under its name rather than theirs. Reading this
table as "DIT spends five billion dollars" would be a misreading.

---

## How far to trust all of this

Two numbers, measured two different ways, both published in full.

**Against the Comptroller's structured dataset**, for the overlap from December
2022:

| Measure | Value |
|---|---|
| Recall | 73.1% (837 of their 1,145 IT rows) |
| Recall, meetings whose summary records actions | 78.1% |
| Precision | 84.0% |
| Meeting date agreement | 100.0% |
| Amount agreement | 98.5% |
| Vendor agreement | 97.0% |
| Contract number agreement | 51.0% |

Contract-number agreement is low for the reason set out above: their field and
mine are often two different identifier systems for the same contract, and
neither is wrong.

**Against the source PDFs**, for the 2016–2022 years where no answer key
exists — a sample of 100 items read by hand, field by field:

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
| **overall** | **97.25%** (22 errors in 800 checks) |

81 of the 100 items were correct in every one of their eight fields. The
worksheet, with a written note on every error, is published as
`hand_audit_holdout.csv`.

The vendor column is the weakest field and the reason is mechanical: vendor
names wrap across lines in a narrow column, and a name that loses its last word
to a line break is the commonest error in the dataset. It is also the most
visible one — `vendor_raw` is published next to `vendor_clean` for exactly this
reason, so a reader can see what the document actually printed.
