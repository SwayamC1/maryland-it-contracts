# Source notes

What the two sources actually contain, written while reading them and added to
every time one of them surprised me. Everything here can be checked against the
untouched files in `data/raw/`.

## Board of Public Works meeting Summary PDFs

`data/raw/manifest.csv` lists all 231, collected 16 September 2026 from
[bpw.maryland.gov](https://bpw.maryland.gov/Pages/meetingDocuments_year.aspx).

The PDFs themselves are not committed - 43MB of documents the state already
publishes - but the manifest carries the URL, byte count and **SHA-256** of
every one, so a re-collection can be checked as byte-identical to the files
these numbers were built from.

The Board meets twice a month. Before each meeting it posts an Agenda; a few
days later it posts a **Summary**, which is the same list of items with the
Board's action noted against each one. The Summary is the file this project
uses.

### Getting the list of files

The year index is reachable as `meetingDocuments_year.aspx?year=YYYY`, so the
links can be read off each year's page. **Do not build the URLs from meeting
dates.** The naming is not consistent - 2017 alone contains
`2017-Jul-5-Summary.pdf`, `2017-June-7-Summary.pdf` and
`2017-Sept-6-Summary.pdf` - and a guessed URL 404s silently, which would show
up months later as a meeting that mysteriously had no IT items.

Meetings found per year: 2016: 23, 2017: 23, 2018: 21, 2019: 23, 2020: 22,
2021: 20, 2022: 17, 2023: 23, 2024: 21, 2025: 21, 2026: 17 (through
16 September). The Board schedules roughly 24 a year, so the lighter years are
worth a note: some scheduled meetings are cancelled and some are not posted as
Summaries.

One link on the state's own 2020 index page is malformed - the February 19,
2020 summary is linked as `https://2019-bpw.maryland.gov/...`, a hostname that
does not resolve. The file exists at the ordinary host and is collected by a
one-line fix-up in `notebooks/01_collect.ipynb`.

### What an item looks like

Five unruled columns:

```
Item   Agency/Institution   County   Vendor, Contractor, Grantee   Description
```

An item begins on a line with something in the Item column, runs for as many
lines as it needs, and is closed by a line reading

```
action: Approved   discussion: No   Doc. No. MDOTTS2608
```

That `Doc. No.` is the state's own contract number and it is the join between
an award and the modifications that follow it years later.

### Five things that broke a first draft of the parser

1. **`extract_table()` returns zero rows.** On every summary tried, 2016
   through 2026. These are not ruled tables; they are positioned text. The
   plan for this project assumed tables would carry most of the work and that
   a model would be needed for the rest. Neither turned out to be true: the
   parser reads word coordinates and needs no model at all.

2. **There are two header layouts and they are not interchangeable.**
   `Item | Institution | County | Vendor | Description` in most files, and
   `Item | Agency | County | Vendor | Description` in others. Assuming the
   first made eleven meetings parse to **zero items with no error**, because
   every word landed in the wrong column. Nothing caught it except the count
   of IT items per meeting printed at the end of a run. Fixing it recovered
   938 items and 87 IT items.

3. **The description column's left margin moves between documents** and is not
   where its own heading sits. It is measured per page instead - the
   description column is the one thing on a page with dozens of lines starting
   at the same x.

4. **The action row is sometimes split in two** by a fraction of a point of
   typesetting, so `action: Approved` and `discussion: No Doc. No. 526SM71430`
   land on separate lines. Left unjoined, two thirds of all items lose their
   action and their contract number.

5. **Agency and county are printed once, on the item's first line.**
   Accumulating them down continuation lines turned an item that adds 113
   master contractors into an agency field holding 113 company names.

### Items with no recorded action

About 5% of items carry no `action:` line. They are concentrated in nine
meetings whose Summary was posted before the meeting and never updated
afterwards - the Board's own page says the Agenda and Summary "may be updated
to reflect revised, supplemental, and hand-carried Items" and are updated again
after the meeting "with notations showing the Board's action on each Item".
Where that second update never happened, no action exists to read.

Those items stay in the published dataset with `action` empty, and are excluded
from every approved-value figure. The affected meetings are listed in
`data/final/md_it_dropped_items.csv`.

### Identifying IT items

Three signals, any one of which is enough:

- the item number carries an `IT` component: `17-IT`, `3-IT-MOD`, `6-IT-OPT`
- the agenda section is an Information Technology section
- the description opens with "Information Technology"

The third matters more than it looks. The Comptroller's own dataset types 731
rows as "Information Technology Contract" that carry no agenda item number at
all, and in the summaries those items are identifiable only by how their
description opens.

## Comptroller BPW Dashboard export

`data/raw/comptroller_bpw_dataset.csv`, 15,242 rows, downloaded 16 September
2026 from
[interactive.marylandcomptroller.gov/BPWDashboard](https://interactive.marylandcomptroller.gov/BPWDashboard)
by clicking Search with no filters and exporting CSV. Covers 7 December 2022
through 5 August 2026. Columns: Agency, Agenda Link, Agenda Item Number,
Category, Type, Description, Amount, Recipient, Certification, Goals, Contract,
Method, Fund Source.

This is the answer key for the overlap years, and it has one feature that has
to be understood before it can be used as one.

**It changes schema partway through.** Rows from 2022, 2025 and 2026 carry an
Agenda Item Number like `DGS 17-IT` and a Type like `Information Technology` or
`Information Technology Modification`. Rows from 2023 and 2024 carry **no item
number at all** and are typed `Information Technology Contract`. Any matching
rule that leans on the item number silently loses two entire years of the
answer key.

| Population | Rows | Years | IT rows |
|---|---|---|---|
| With an Agenda Item Number | 7,117 | 2022, 2025, 2026 | 454 |
| Without one | 8,125 | 2023, 2024 | 731 |

Every IT row carries a Contract value, sometimes several separated by `;` or
`/`, and sometimes the literal string "No Contract Number Listed". That field
is what makes contract-number matching possible for the two years with no item
numbers.

The dashboard's own disclaimer is worth quoting in full, because it is also the
argument for this project existing: the meeting documents "take precedence over
any information presented in the dashboard in the event of a discrepancy".
