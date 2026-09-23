# Data dictionary

Every published row carries `source_pdf` and `source_page`, so any figure can be
checked against the state's own document in under a minute. That property is the
point of the dataset.

**All money is approved contract value** - a ceiling the Board authorised, not
money the state spent. `amount_basis` says which kind of figure it was.

## data/final/md_it_contracts.csv

One row per approved IT agenda item.

| Column | Type | Meaning |
|---|---|---|
| `meeting_date` | date | Board meeting, from the Summary filename via the collection manifest |
| `agenda` | text | the `Agenda:` section the item sat under, e.g. `Department of Information Technology` |
| `doc_number` | text | the item number as printed, e.g. `17-IT`, `3-IT-MOD`, `6-IT-OPT` |
| `item_type` | text | `award`, `modification`, `renewal`, `confirmation` |
| `agency` | text | agency or institution code as printed, e.g. `DOT/SHA`, `DIT`, `EDUC` |
| `county` | text | county or `Statewide` |
| `vendor_raw` | text | the vendor column exactly as printed |
| `vendor_clean` | text | normalised and merged; empty where the item names no single vendor |
| `description` | text | the description column, joined across the item's lines |
| `amount_usd` | number | the approved figure in whole dollars |
| `amount_basis` | text | `not-to-exceed`, `fixed`, `estimated`, `no change`, `revenue-to-state` |
| `term_start`, `term_end` | date | from `Term: 4/20/26 - 4/19/28` |
| `action` | text | the Board's action, e.g. `Approved` |
| `discussion` | text | whether the item was discussed |
| `references_doc` | text | cross references found in the description, `;` separated |
| `contract_id` | text | the state's document number, from `Doc. No.` on the action line |
| `multi_vendor` | 0/1 | the item covers several companies, so its money is not one vendor's |
| `source_pdf` | text | the Summary PDF; also the filename at `bpw.maryland.gov/MeetingDocs/` |
| `source_page` | int | page within that PDF |

Empty always means "not stated in the document". It never means zero.

## data/final/md_it_contract_rollup.csv

One row per contract number, built by grouping items on `contract_id` with
`references_doc` as a fallback.

| Column | Meaning |
|---|---|
| `contract_id` | the state document number the items share |
| `agency`, `vendor_clean` | from the earliest item on the contract |
| `n_items`, `n_awards`, `n_changes` | items on this contract, and the award/change split |
| `first_item_date`, `last_item_date` | span of Board activity on it |
| `original_approved_usd` | the first award's approved figure |
| `later_approved_usd` | every modification, renewal and option added together |
| `total_approved_usd` | original plus later |
| `growth_usd`, `growth_pct` | total minus original, and that as a percentage |
| `months_to_first_change` | months from the award meeting to the first later item |
| `in_growth_analysis` | 1 if the contract qualifies, 0 otherwise |
| `exclusion_reason` | why it does not qualify, when it does not |
| `multi_vendor` | 1 if any item on it covers several companies |

A contract is in the growth analysis only if its **original award** is inside
the window, the award has a dollar figure, it was awarded **through 2022** so it
has had at least three years in which it could have been modified, and no item
on it covers several vendors.

## Other published files

| File | What it holds |
|---|---|
| `md_it_dropped_items.csv` | every IT item not counted, with the reason |
| `md_it_rollup_dropped.csv` | every contract outside the growth analysis, with the reason |
| `validation_summary.csv` | recall, precision and per-field agreement against the Comptroller's dataset |
| `validation_misses.csv` | their IT rows my pipeline did not find |
| `validation_extras.csv` | my IT items that matched none of theirs |
| `validation_disagreements.csv` | matched rows where a field disagrees, with both values and the source page |
| `analysis_q1` … `analysis_q6` | the output of each question in `src/analyse.py` |
| `data/interim/vendor_merges.csv` | every proposed vendor merge, with the `keep` decision made by hand |
| `data/raw/manifest.csv` | every Summary PDF collected: year, meeting date, URL, bytes, status |

## Units and conventions

- Money is whole US dollars.
- Dates are ISO `YYYY-MM-DD`. Two-digit years in the source (`4/19/28`) are read
  as 20xx.
- `meeting_date` is the Board meeting the item was approved at, not the contract
  start date.
- Years are calendar years. 2026 is partial, through 16 September.
