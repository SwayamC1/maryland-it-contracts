# Build log

What I tried, what broke, and what I expected before I ran it. Kept because the
dead ends are where I learned what these documents actually are, and because a
clean repo with no record of the mess is not an honest one.

---

## Predictions, written before the queries were run

These are here in full, including the ones that turned out wrong. The gap
between a prediction and a result is the most useful thing in the project.

**Q1, approved IT value by year.** I expect a rising line, steeper after 2020,
with a visible COVID dip in 2020 and a jump in 2021-22 as remote-work
infrastructure was bought. I also expect 2026 to look small because it is a
partial year.

**Q2, top vendors.** I expect heavy concentration - the top 10 holding more
than half of all approved value - and I expect the names to be reseller and
staffing firms rather than the software companies whose products the state
actually runs. Task orders go to the holder of the master contract, not to the
manufacturer.

**Q3, median growth from award to total approved.** I expect something in the
range of 10 to 25%. My reasoning: most contracts are never modified at all, so
the median is dragged toward zero, but the ones that are modified tend to be
modified substantially.

**Q4, the distribution.** I expect a large "no change" group, a thin middle,
and a long right tail containing a handful of contracts that more than doubled.
If the median is small and the tail is fat, the median is the wrong statistic to
lead with and the distribution is the finding.

**Q5, time from award to first modification.** I expect a peak somewhere around
12 to 24 months - the end of a first option year - rather than a smooth decay.

**Q6, growth by agency.** I expect the transportation and health agencies to
show the most growth, on the theory that their systems are the largest and the
most entangled with federal requirements.

**Validation.** I expect recall in the low 90s and per-field agreement above
95% on dates, high on vendor, and lowest on amount - because amounts are where
an item with a retroactive part and a proactive part can legitimately be read
two ways.

---

## Day 1, reading before writing

Opened a 2026, a 2021 and a 2017 summary side by side. The item table is laid
out the same way in all three, so the window holds at 2016.

**`extract_table()` returns zero rows.** On every summary tried. The plan this
project was built from assumed these were ruled tables and that a model would
be needed only for the rows that did not parse cleanly. Neither is true: they
are unruled positioned text in five columns, and reading word coordinates
handles all of it. So the pipeline has no model in it anywhere, and the number
I report is not "80% parsed deterministically" but "all of it did".

## Day 2, collecting

The year index is reachable as `?year=YYYY`, so links can be read off each
page rather than constructed. That turned out to matter: 2017 alone contains
`2017-Jul-5-Summary.pdf`, `2017-June-7-Summary.pdf` and
`2017-Sept-6-Summary.pdf`.

**One link on the state's own page is broken.** The February 19, 2020 summary
is linked as `https://2019-bpw.maryland.gov/...` - a hostname that does not
resolve. The file is fine at the real host. Collected 230 on the first pass,
231 after a one-line fix-up.

My own machine sits behind a proxy that does not allow `maryland.gov`, so
collection runs in Google Colab, which has ordinary internet. That is the only
reason there is a notebook in this repo.

## Days 3 to 4, parsing

**The bug that would have ruined the project.** Eleven meetings parsed to zero
items. No exception, no warning - every word landed in the wrong column and no
line matched an item pattern. The cause: there are **two header layouts**,

```
Item | Institution | County | Vendor, Contractor, Grantee | Description
Item | Agency      | County | Vendor, Contractor, Grantee | Description
```

and I had hard-coded the first. The only thing that caught it was a count of IT
items per meeting printed at the end of every run, which the plan told me to
add for exactly this reason. Fixing it recovered 938 items and 87 IT items.

That check is now permanent, and the lesson is in the parser docstring: a
positional parser that finds nothing looks identical to a meeting that had
nothing.

**The description column's left margin is not where its heading is.** In some
documents the Description heading sits above its own body; in others it sits to
the left of it, and the body's margin moves between documents anyway. So it is
measured per page - the description column is the one thing on a page with
dozens of lines starting at the same x.

**Two thirds of items lost their action line** on the first attempt, because
`action: Approved` and `discussion: No Doc. No. 526SM71430` are one printed row
typeset a fraction of a point apart, and the line grouper split them. Rejoining
them took the miss rate from 67% to 3%.

**An item that adds 113 master contractors** put 113 company names into its
agency field, because I was accumulating agency and county down continuation
lines. They are printed once, on the item's first line. Those multi-vendor
items are now flagged and kept out of vendor rankings, since the money is real
but does not belong to one company.

**About 5% of items have no action at all.** Not a parser failure: those
meetings' summaries were posted before the meeting and never updated with the
Board's actions. They stay in the dataset with `action` empty and are excluded
from every approved-value figure.

## Day 5, the grain problem

Recall against the Comptroller's dataset came out at **31%**, which was so bad
it had to be a misunderstanding rather than a bug. It was. From about 2020 the
summaries stop printing one vendor per IT item and start printing an item that
says "Approve ten Task Orders under previously-approved master contracts",
followed by a numbered table - `1.1`, `1.2`, `2.1` - each row its own agency,
its own vendor, its own money. The Comptroller's dataset has a row per **task
order**. I had a row per **agenda item**.

Parsing the sub-items took recall from 31% to 60%, and then to 67% once the
sub-items inherited their parent's Board action - the `action:` line is printed
after the whole item, so at the moment a sub-item is built its parent does not
have one yet.

The sub-items are kept in the same file, with `parent_item` set, and Q1 reports
agenda items and bundled task orders as **two separate columns**. Adding them
would make 2019 and 2021 incomparable, because the second column does not exist
before 2020.

## Day 7, validating

**The answer key changes schema partway through.** The Comptroller's rows from
2022, 2025 and 2026 carry an Agenda Item Number and types like "Information
Technology Modification". Rows from 2023 and 2024 carry no item number at all
and are typed "Information Technology Contract". A matching rule built on item
numbers loses two entire years without saying so, which is why matching runs in
three passes: item number, then contract number, then vendor and amount.

That discovery also changed the extraction. Since 731 of their IT rows have no
item number, the summaries must be identifying those items some other way - and
they are, by opening the description with "Information Technology". That became
the third IT classifier.

## Day 7, the hand audit

The benchmark says nothing about 2016 to 2022, because the answer key does not
start until December 2022. The only way to put a number on those years is to
open the PDFs and read them, so `src/hand_audit.py` draws a sample and pulls
the text printed around each sampled item, and I read the two against each
other field by field.

I did this **twice, on two independent samples**, and the reason is worth
writing down. The first sample of 100 found real bugs, I fixed them, and the
accuracy figure from that same sample was then worthless - I had tuned the
parser on the very items I was scoring. So the first pass is a debugging pass
and its number is not published. A second sample of 100, drawn with a different
seed and never looked at until the parser was frozen, is the one the README
reports.

Both worksheets are published anyway - `hand_audit_pre2022.csv` and
`hand_audit_holdout.csv` - so the sampling can be rebuilt and the reading
disagreed with.

What the first pass found, all of it now fixed:

- A sub-item's **county was ending up in its agency** - "ELECTLAW Statewide"
  rather than "ELECTLAW" - because a sub-item row is shifted one column left of
  where the parent prints it. 663 rows.
- **The description column has two left margins on the same page**: 452 for the
  main item table and 471 for the task-order tables inside an item. Taking the
  more common of the two put the first word of every main-table description
  line in the vendor column, which is how "StreetLight Data, Inc." became
  "StreetLight Data, Inc. Information platform devices."
- "approved with revisions" was recorded as **"approved with"**, because the
  action column is narrow and "revisions" wraps onto a line of its own.
- The first money label in a sentence **swallowed the rest of it**, so
  "Retroactive Amount: $311,903, Proactive Amount: $732,542, Total Amount:
  $1,044,445" was read as $311,903.
- A **reduction** - "Reduction Amount: ($667,045)", "Amount: -$5,735,654
  (decrease)" - was being added rather than subtracted.
- "Amount:$10 million" was read as **ten dollars**.
- An item with a retroactive half and a proactive half recorded **only the
  retroactive term**, so a five-year award looked like a two-week one.
- The vendor label was chosen by frequency, and where a name wraps onto the
  next line the **truncated spelling is the more common one** - "Business
  Solutions Group," beat "Business Solutions Group, LLC" on a straight vote.
- "VARIOUS" in capitals was not recognised as the **no-single-vendor
  placeholder**, though "Various" was.
- An item numbered `-OPT` was typed as a modification whenever the word
  "Modification" appeared anywhere in its description, including inside the
  money label "Modification Amount:". The item number is now read first and on
  its own.

The second pass, on the held-out sample, is the published number. What it found
is in the README, and the errors it turned up have been fixed too - which means
the published figure is a **lower bound** on the accuracy of the dataset as it
now stands, measured before those last fixes went in. It is not adjusted
upwards afterwards, because that would be the same circularity again.

## Day 8, the finding I did not want

Linking a modification to the contract it modifies is the whole point of the
growth question, and for most modifications **it cannot be done from the
Summaries alone.**

Maryland uses two identifier systems in the same column. An award carries a
procurement contract number - `F50B2600034`. A modification usually carries a
**change-order control number** - `COL26444` - which appears nowhere else in the
Summary, not on the award it changes and not on any other item. The Comptroller's
dataset occasionally prints both in its Contract field separated by " / ", and a
crosswalk built from those resolved a handful of them; the rest cannot be joined
without a data source neither published file contains.

So the growth analysis runs on the contracts that can be linked, the number of
contracts it runs on is published next to the result, and the headline is not
the growth figure. Reporting a median growth rate off a linkable minority and
presenting it as "how much Maryland IT contracts grow" would be the kind of
number this project exists to avoid.

---

## Still open

- Vendor merges above the fuzzy threshold are reviewed by hand and the decision
  list is committed, but the threshold itself is a judgement call. Ten further
  merges were added by hand after the audit, mostly bare acronyms - "SHI" for
  SHI International, "Esri" for Environmental Systems Research Institute - that
  are too short for any fuzzy score to propose.
- An item with a Part A and a Part B and no printed total is recorded at the
  value of Part A. Where the two halves are labelled Retroactive and Proactive,
  or Extension, they are added; where they are labelled "PART A" and "PART B"
  they are not, because a bare second "Amount:" is more often a restatement
  than a second half and adding those would double-count.
- A handful of "record correction" items reprint the whole procurement summary
  box - Contract Term, Procurement Method, Number of Bids - down the middle of
  the page, and those lines land in the vendor column. Six items in the dataset
  look like this. They are visible immediately in the published CSV because
  their `vendor_raw` contains the words "Procurement Method".
- `references_doc` catches cross references in the description text, but an
  item that refers to a prior approval only in prose ("the contract approved in
  April 2019") is not captured.
- Nothing here has been read by anyone who works in Maryland procurement. That
  is the next step and it belongs in the README when it happens, not before.
