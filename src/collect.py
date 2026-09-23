"""
Collect Board of Public Works meeting Summary PDFs.

Runs anywhere with internet. It is written to be run from a Google Colab cell,
because that is where this project's downloading happened - my own machine sits
behind a proxy that does not allow maryland.gov, and Colab does not.

Two rules this follows, both learned the hard way and both worth keeping:

  * Read the PDF links off each year's index page. Do not build URLs from the
    meeting date. The file naming is not consistent - 2017 alone contains
    2017-Jul-5-Summary.pdf, 2017-June-7-Summary.pdf and 2017-Sept-6-Summary.pdf
    - and a guessed URL 404s silently, which shows up later as a meeting that
    mysteriously had no IT items.
  * One second between requests. This is a small state agency's web server and
    there is no reason to hammer it.
"""

import argparse
import csv
import os
import re
import time
import urllib.parse

import requests

INDEX = "https://bpw.maryland.gov/Pages/meetingDocuments_year.aspx?year=%d"
SUMMARY_LINK = re.compile(r'href="([^"]*?/MeetingDocs/[^"]*?Summary\.pdf)"', re.I)
DATE_IN_NAME = re.compile(r"(\d{4})-([A-Za-z]+)-(\d{1,2})-Summary\.pdf", re.I)

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
          "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
          "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
          "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11,
          "dec": 12, "december": 12}

HEADERS = {"User-Agent": "md-it-contracts research collector (student project)"}


def meeting_date(filename):
    """'2017-Sept-6-Summary.pdf' -> '2017-09-06', or None if it does not parse."""
    m = DATE_IN_NAME.search(filename)
    if not m:
        return None
    year, month, day = m.group(1), m.group(2).lower(), int(m.group(3))
    if month not in MONTHS:
        return None
    return "%s-%02d-%02d" % (year, MONTHS[month], day)


def links_for_year(session, year):
    """Every Summary PDF URL on a year's index page, in page order."""
    r = session.get(INDEX % year, headers=HEADERS, timeout=60)
    r.raise_for_status()
    seen, out = set(), []
    for href in SUMMARY_LINK.findall(r.text):
        url = urllib.parse.urljoin("https://bpw.maryland.gov/", href)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2016)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--out", default="pdfs")
    ap.add_argument("--manifest", default="manifest.csv")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    session = requests.Session()
    rows = []

    for year in range(args.start, args.end + 1):
        try:
            urls = links_for_year(session, year)
        except Exception as exc:                      # noqa: BLE001
            print("%d  INDEX FAILED  %s" % (year, exc))
            continue
        print("%d  %d summaries on the index page" % (year, len(urls)))
        for url in urls:
            name = os.path.basename(urllib.parse.urlparse(url).path)
            path = os.path.join(args.out, name)
            if os.path.exists(path) and os.path.getsize(path) > 10000:
                status, size = "cached", os.path.getsize(path)
            else:
                time.sleep(args.pause)
                try:
                    resp = session.get(url, headers=HEADERS, timeout=120)
                except Exception as exc:              # noqa: BLE001
                    print("    FAILED %s  %s" % (name, exc))
                    rows.append({"year": year, "meeting_date": meeting_date(name),
                                 "url": url, "filename": name, "bytes": 0,
                                 "status": "error"})
                    continue
                if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
                    # A 200 that is not a PDF means the link went to a landing
                    # page. Record it rather than writing a broken file.
                    print("    NOT A PDF %s  http=%s" % (name, resp.status_code))
                    rows.append({"year": year, "meeting_date": meeting_date(name),
                                 "url": url, "filename": name, "bytes": 0,
                                 "status": "not_pdf_%s" % resp.status_code})
                    continue
                with open(path, "wb") as fh:
                    fh.write(resp.content)
                status, size = "downloaded", len(resp.content)
            rows.append({"year": year, "meeting_date": meeting_date(name),
                         "url": url, "filename": name, "bytes": size,
                         "status": status})

    with open(args.manifest, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["year", "meeting_date", "url",
                                           "filename", "bytes", "status"])
        w.writeheader()
        w.writerows(rows)

    ok = [r for r in rows if r["status"] in ("downloaded", "cached")]
    bad = [r for r in rows if r not in ok]
    undated = [r for r in ok if not r["meeting_date"]]
    print("\n%d summaries collected, %d failed, %d filenames with no parseable date"
          % (len(ok), len(bad), len(undated)))
    for r in bad:
        print("  failed:", r["filename"], r["status"])
    for r in undated:
        print("  no date:", r["filename"])


if __name__ == "__main__":
    main()
