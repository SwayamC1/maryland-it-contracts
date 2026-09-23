"""
The six figures, each carrying one finding.

Rules followed here, and they are the reason the charts read on a phone:
full sentences as titles, direct labels instead of legends, one accent colour
with grey for everything else, and type sized for a small screen.

Two files come out of each figure, light and dark, because a PNG cannot respond
to the reader's colour scheme and the README picks between them with <picture>.

Figure 6 charts the pipeline's own error rate. Almost nobody publishes that,
and it reads as confidence rather than hedging.
"""

import csv
import os
import textwrap
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = os.path.join(HERE, "..", "data", "final")
FIGURES = os.path.join(HERE, "..", "figures")

# Validated three-slot categorical palette plus chart chrome. The three hues
# clear colour-blind separation on every pair in both modes; only three are
# used, and every coloured mark is directly labelled as well.
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "secondary": "#52514e",
              "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
              "grey": "#c9c8c1",
              "accent": "#2a78d6", "warm": "#eb6834", "cool": "#1baf7a"},
    "dark": {"surface": "#1a1a19", "ink": "#ffffff", "secondary": "#c3c2b7",
             "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835",
             "grey": "#4a4a47",
             "accent": "#3987e5", "warm": "#d95926", "cool": "#199e70"},
}


def read(name):
    path = os.path.join(FINAL, name)
    if not os.path.exists(path):
        return None
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def frame(t, size=(9, 5.4)):
    fig, ax = plt.subplots(figsize=size, dpi=200)
    fig.patch.set_facecolor(t["surface"])
    ax.set_facecolor(t["surface"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["axis"])
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=t["muted"], labelsize=11, length=0)
    ax.set_axisbelow(True)
    return fig, ax


def wrap(text, width):
    """Hard-wrap, keeping any line breaks the caller put in deliberately."""
    return "\n".join("\n".join(textwrap.wrap(part, width)) if part else ""
                     for part in text.split("\n"))


def finish(fig, ax, t, name, title, subtitle, note):
    title = wrap(title, 62)
    top = 0.965
    fig.text(0.055, top, title, color=t["ink"], fontsize=15.5,
             fontweight="bold", va="top", linespacing=1.25)
    drop = 0.062 * title.count("\n") + 0.072
    if subtitle:
        fig.text(0.055, top - drop, wrap(subtitle, 95), color=t["secondary"],
                 fontsize=11, va="top", linespacing=1.35)
        drop += 0.045 * (wrap(subtitle, 95).count("\n") + 1)
    if note:
        fig.text(0.055, 0.03, wrap(note, 108), color=t["muted"], fontsize=9,
                 va="bottom", linespacing=1.5)
    fig.subplots_adjust(left=fig.subplotpars.left, right=0.955,
                        top=0.965 - drop - 0.02, bottom=0.19)
    os.makedirs(FIGURES, exist_ok=True)
    fig.savefig(os.path.join(FIGURES, name), facecolor=t["surface"])
    plt.close(fig)


def dollars(x, _pos=None):
    if abs(x) >= 1e9:
        return "$%.1fB" % (x / 1e9)
    if abs(x) >= 1e6:
        return "$%.0fM" % (x / 1e6)
    return "$%.0f" % x


# ------------------------------------------------------------------ fig 1 ---
def fig_by_year(theme):
    rows = read("analysis_q1_by_year.csv")
    if not rows:
        return
    t = THEMES[theme]
    years = [int(r["year"]) for r in rows]
    base = [num(r["approved_usd_agenda_items"]) or 0 for r in rows]
    extra = [num(r["approved_usd_bundled_task_orders"]) or 0 for r in rows]
    vals = [a + b for a, b in zip(base, extra)]
    fig, ax = frame(t)
    ax.bar(years, base, color=t["accent"], width=0.72)
    ax.bar(years, extra, bottom=base, color=t["grey"], width=0.72)
    ax.annotate("task orders bundled\ninside an item", xy=(2021, base[5] + extra[5]),
                xytext=(0, 10), textcoords="offset points", color=t["secondary"],
                fontsize=10, ha="center")
    ax.annotate("items as listed\non the agenda", xy=(2017, base[1]),
                xytext=(0, 10), textcoords="offset points", color=t["accent"],
                fontsize=10, fontweight="bold", ha="center")
    ax.axvline(2022.5, color=t["warm"], linewidth=1.6, linestyle=(0, (4, 3)))
    ax.annotate("the state's own structured\ndataset starts here",
                xy=(2022.5, max(vals) * 0.98), xytext=(6, 0),
                textcoords="offset points", color=t["warm"], fontsize=10,
                fontweight="bold", va="top")
    ax.yaxis.set_major_formatter(FuncFormatter(dollars))
    ax.yaxis.grid(True, color=t["grid"], linewidth=0.8)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=0)
    finish(fig, ax, t, "fig1_approved_by_year_%s.png" % theme,
           "Seven of these eleven years had no structured public record",
           "Approved value of Board of Public Works IT items, by calendar year.",
           "Approved value is a ceiling the Board authorised, not money spent. "
           "2026 is a partial year, through 16 September.\n"
           "The summaries only began listing bundled task orders as numbered "
           "sub-items around 2020, so totals before and after that are not "
           "strictly comparable.")


# ------------------------------------------------------------------ fig 2 ---
def fig_award_vs_total(theme):
    rows = read("analysis_q3_growth.csv")
    if not rows:
        return
    t = THEMES[theme]
    pts = [(num(r["original_approved_usd"]), num(r["total_approved_usd"]))
           for r in rows]
    pts = [(a, b) for a, b in pts if a and b and a > 0 and b > 0]
    if not pts:
        return
    fig, ax = frame(t)
    grew = [(a, b) for a, b in pts if b > a * 1.0001]
    same = [(a, b) for a, b in pts if b <= a * 1.0001]
    ax.scatter([a for a, _ in same], [b for _, b in same], s=26,
               color=t["grey"], edgecolors="none", label="unchanged")
    ax.scatter([a for a, _ in grew], [b for _, b in grew], s=30,
               color=t["accent"], alpha=0.75, edgecolors="none", label="grew")
    lo = min(min(a for a, _ in pts), min(b for _, b in pts))
    hi = max(max(a for a, _ in pts), max(b for _, b in pts))
    ax.plot([lo, hi], [lo, hi], color=t["muted"], linewidth=1.2,
            linestyle=(0, (4, 3)))
    ax.annotate("no change", xy=(hi, hi), xytext=(-6, 8),
                textcoords="offset points", color=t["muted"], fontsize=10,
                ha="right")
    ax.annotate("%d grew" % len(grew),
                xy=(lo * 3, hi * 0.6), color=t["accent"], fontsize=11,
                fontweight="bold")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(dollars))
    ax.yaxis.set_major_formatter(FuncFormatter(dollars))
    ax.set_xlabel("original approved award", color=t["secondary"], fontsize=11)
    ax.set_ylabel("total approved after all changes", color=t["secondary"],
                  fontsize=11)
    ax.grid(True, color=t["grid"], linewidth=0.7)
    finish(fig, ax, t, "fig2_award_vs_total_%s.png" % theme,
           "Everything above the line is a contract that grew after it was approved",
           "One dot per contract. Both axes are log scale, because the "
           "contracts span five orders of magnitude.",
           "Contracts awarded through 2022 only, so each has had at least "
           "three years in which it could have been modified.")


# ------------------------------------------------------------------ fig 3 ---
def fig_growth_distribution(theme):
    rows = read("analysis_q4_growth_distribution.csv")
    if not rows:
        return
    t = THEMES[theme]
    labels = [r["bucket"] for r in rows]
    vals = [int(r["contracts"]) for r in rows]
    fig, ax = frame(t)
    bars = ax.barh(range(len(labels)), vals, color=t["grey"], height=0.68)
    for i, (b, lab) in enumerate(zip(bars, labels)):
        if lab in ("100 to 300%", "over 300%"):
            b.set_color(t["warm"])
    fig.subplots_adjust(left=0.20)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, max(vals) * 1.12)
    ax.invert_yaxis()
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
    for i, v in enumerate(vals):
        ax.annotate(str(v), xy=(v, i), xytext=(5, 0),
                    textcoords="offset points", va="center",
                    color=t["secondary"], fontsize=10)
    finish(fig, ax, t, "fig3_growth_distribution_%s.png" % theme,
           "The median hides the tail, and the tail is the story",
           "Contracts by how far their approved value moved between the "
           "original award and the total after every later change.",
           "Growth is not waste. Contracts grow for scope changes, term "
           "extensions, federal requirements and emergencies.")


# ------------------------------------------------------------------ fig 4 ---
def fig_top_vendors(theme):
    rows = read("analysis_q2_vendors.csv")
    if not rows:
        return
    t = THEMES[theme]
    rows = rows[:15][::-1]
    labels = [r["vendor"][:34] for r in rows]
    vals = [num(r["approved_usd"]) or 0 for r in rows]
    fig, ax = frame(t, size=(9, 6.2))
    fig.subplots_adjust(left=0.30)
    ax.barh(range(len(labels)), vals, color=t["accent"], height=0.7)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(dollars))
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
    for i, v in enumerate(vals):
        ax.annotate(dollars(v), xy=(v, i), xytext=(5, 0),
                    textcoords="offset points", va="center",
                    color=t["secondary"], fontsize=9.5)
    finish(fig, ax, t, "fig4_top_vendors_%s.png" % theme,
           "Fifteen companies hold most of Maryland's approved IT contract value",
           "Total approved value across all IT items, 2016 to 2026.",
           "Items covering several vendors at once are excluded - that money "
           "is real but it does not belong to one company.")


# ------------------------------------------------------------------ fig 5 ---
def fig_months_to_change(theme):
    rows = read("analysis_q5_months_to_first_change.csv")
    if not rows:
        return
    t = THEMES[theme]
    starts = [int(r["months_bucket_start"]) for r in rows]
    vals = [int(r["contracts"]) for r in rows]
    fig, ax = frame(t)
    ax.bar(starts, vals, width=5.2, align="edge", color=t["cool"])
    ax.set_xlabel("months from award to first modification",
                  color=t["secondary"], fontsize=11)
    ax.yaxis.grid(True, color=t["grid"], linewidth=0.8)
    ax.set_xticks(starts)
    ax.set_xticklabels([str(s) for s in starts], fontsize=10)
    finish(fig, ax, t, "fig5_months_to_first_change_%s.png" % theme,
           "Most contracts that change are changed within their first two years",
           "Contracts that were modified at least once, by how long the first "
           "change took. The last bucket holds everything at 60 months or more.",
           "Counted from the meeting that approved the award to the meeting "
           "that approved the first later item on the same contract number.")


# ------------------------------------------------------------------ fig 6 ---
def fig_validation(theme):
    rows = read("validation_summary.csv")
    if not rows:
        return
    t = THEMES[theme]
    pretty = {"recall_pct": "recall",
              "recall_actioned_meetings_pct": "recall, meetings\nthat record actions",
              "precision_pct": "precision",
              "meeting_date_agreement_pct": "meeting date",
              "amount_agreement_pct": "amount",
              "vendor_agreement_pct": "vendor",
              "contract_agreement_pct": "contract number"}
    rows = [r for r in rows if r["measure"] in pretty]
    labels = [pretty[r["measure"]] for r in rows][::-1]
    vals = [num(r["value"]) or 0 for r in rows][::-1]
    dens = [r["denominator"] for r in rows][::-1]
    fig, ax = frame(t, size=(9, 5.6))
    bars = ax.barh(range(len(labels)), vals, color=t["grey"], height=0.62)
    for b, v in zip(bars, vals):
        b.set_color(t["cool"] if v >= 95 else t["warm"] if v < 85 else t["accent"])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(0, 128)
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
    for i, (v, d) in enumerate(zip(vals, dens)):
        ax.annotate("%.1f%%  of %s" % (v, d), xy=(v, i), xytext=(6, 0),
                    textcoords="offset points", va="center",
                    color=t["secondary"], fontsize=10)
    fig.subplots_adjust(left=0.24)
    finish(fig, ax, t, "fig6_validation_%s.png" % theme,
           "How often this pipeline agrees with the state's own dataset",
           "Measured over every meeting both cover, December 2022 to August "
           "2026. Each field reported separately.",
           "Every unmatched row on either side is published in "
           "data/final/validation_misses.csv and validation_extras.csv.")


def main():
    for theme in THEMES:
        for fn in (fig_by_year, fig_award_vs_total, fig_growth_distribution,
                   fig_top_vendors, fig_months_to_change, fig_validation):
            try:
                fn(theme)
            except Exception as exc:                       # noqa: BLE001
                print("   %s (%s) failed: %s" % (fn.__name__, theme, exc))
    made = sorted(os.listdir(FIGURES)) if os.path.isdir(FIGURES) else []
    print("wrote %d figure files" % len(made))
    for name in made:
        print("   " + name)


if __name__ == "__main__":
    main()
