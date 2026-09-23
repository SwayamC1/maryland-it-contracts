"""
What Maryland actually pays for IT - the explorer.

Three screens: look up a vendor, walk a contract from award through every later
change, and read the findings with the figures.

Everything on every screen carries the source PDF and page it came from,
because the point of the dataset is that any number in it can be checked
against the state's own document in under a minute.
"""

import os

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "final")
FIGURES = os.path.join(HERE, "..", "figures")
DOCS = os.path.join(HERE, "..", "docs")

BPW_DOC = "https://bpw.maryland.gov/MeetingDocs/%s"

st.set_page_config(page_title="What Maryland pays for IT",
                   page_icon="MD", layout="wide")


@st.cache_data
def load():
    items = pd.read_csv(os.path.join(DATA, "md_it_contracts.csv"))
    rollup = pd.read_csv(os.path.join(DATA, "md_it_contract_rollup.csv"))
    items["meeting_date"] = pd.to_datetime(items["meeting_date"],
                                           errors="coerce")
    items["year"] = items["meeting_date"].dt.year
    items["amount_usd"] = pd.to_numeric(items["amount_usd"], errors="coerce")
    items["multi_vendor"] = pd.to_numeric(items["multi_vendor"],
                                          errors="coerce").fillna(0)
    return items, rollup


@st.cache_data
def load_csv(name):
    path = os.path.join(DATA, name)
    return pd.read_csv(path) if os.path.exists(path) else None


def money(x):
    if pd.isna(x):
        return "-"
    if abs(x) >= 1e9:
        return "$%.2fB" % (x / 1e9)
    if abs(x) >= 1e6:
        return "$%.1fM" % (x / 1e6)
    return "${:,.0f}".format(x)


def source_link(row):
    return BPW_DOC % row["source_pdf"]


items, rollup = load()
validation = load_csv("validation_summary.csv")

st.title("What Maryland actually pays for IT")
st.caption(
    "Board of Public Works IT contract approvals, %s to %s, structured from "
    "the meeting summary PDFs. **These are approved ceilings, not money "
    "spent** - an item reading \"Not to Exceed $390,000\" means the state may "
    "spend up to that, not that it did."
    % (items["meeting_date"].min().date(), items["meeting_date"].max().date()))

tab_vendor, tab_contract, tab_findings = st.tabs(
    ["Vendor", "Contract", "Findings"])

# ---------------------------------------------------------------- vendor ---
with tab_vendor:
    st.subheader("Look up a company")
    named = items[(items["multi_vendor"] == 0) & items["vendor_clean"].notna()]
    vendors = sorted(v for v in named["vendor_clean"].unique() if str(v).strip())
    picked = st.selectbox("Vendor", vendors, index=None,
                          placeholder="Start typing a company name")
    if picked:
        rows = named[named["vendor_clean"] == picked].sort_values("meeting_date")
        c1, c2, c3 = st.columns(3)
        c1.metric("Approved value", money(rows["amount_usd"].sum()))
        c2.metric("Items", len(rows))
        c3.metric("Contracts", rows["contract_id"].nunique())
        table = rows.assign(
            date=rows["meeting_date"].dt.date,
            approved=rows["amount_usd"].map(money),
            source=rows.apply(source_link, axis=1),
        )[["date", "doc_number", "item_type", "agency", "contract_id",
           "approved", "amount_basis", "source_page", "description", "source"]]
        st.dataframe(table, hide_index=True, use_container_width=True,
                     column_config={"source": st.column_config.LinkColumn(
                         "source PDF", display_text="open")})
    else:
        top = (named.groupby("vendor_clean")["amount_usd"].sum()
               .sort_values(ascending=False).head(25).reset_index())
        top["approved"] = top["amount_usd"].map(money)
        st.caption("Top 25 vendors by approved value. Items covering several "
                   "vendors at once are excluded - that money is real but it "
                   "does not belong to one company.")
        st.dataframe(top[["vendor_clean", "approved"]], hide_index=True,
                     use_container_width=True)

# -------------------------------------------------------------- contract ---
with tab_contract:
    st.subheader("Follow a contract from award to every later change")
    ids = sorted(str(c) for c in rollup["contract_id"].dropna().unique())
    cid = st.selectbox("Contract number", ids, index=None,
                       placeholder="e.g. F50B6600017")
    if cid:
        head = rollup[rollup["contract_id"] == cid].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Original award", money(head["original_approved_usd"]))
        c2.metric("Total approved", money(head["total_approved_usd"]))
        c3.metric("Change", money(head["growth_usd"]))
        c4.metric("Growth", "-" if pd.isna(head["growth_pct"])
                  else "%.1f%%" % head["growth_pct"])
        if str(head["exclusion_reason"]).strip() not in ("", "nan"):
            st.info("Not in the growth analysis: %s" % head["exclusion_reason"])
        rows = items[items["contract_id"] == cid].sort_values("meeting_date")
        table = rows.assign(
            date=rows["meeting_date"].dt.date,
            approved=rows["amount_usd"].map(money),
            source=rows.apply(source_link, axis=1),
        )[["date", "doc_number", "item_type", "vendor_raw", "approved",
           "amount_basis", "term_start", "term_end", "source_page",
           "description", "source"]]
        st.dataframe(table, hide_index=True, use_container_width=True,
                     column_config={"source": st.column_config.LinkColumn(
                         "source PDF", display_text="open")})

# -------------------------------------------------------------- findings ---
with tab_findings:
    path = os.path.join(DOCS, "findings.md")
    if os.path.exists(path):
        st.markdown(open(path).read())
    if os.path.isdir(FIGURES):
        for name in sorted(os.listdir(FIGURES)):
            if name.endswith("_light.png"):
                st.image(os.path.join(FIGURES, name), use_container_width=True)
    if validation is not None:
        st.subheader("How accurate is this?")
        st.caption("Measured against the Comptroller's own dataset over every "
                   "meeting both cover. Misses and disagreements are published "
                   "in the repo rather than summarised away.")
        st.dataframe(validation, hide_index=True, use_container_width=True)
