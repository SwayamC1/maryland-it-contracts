"""
Run the whole pipeline in order, from the raw PDFs to the figures.

Each step is also runnable on its own. They are separate scripts rather than
one module because when a source changes shape it is always one step that
breaks, and it should be obvious which.

Collection is deliberately NOT in here. It hits a state web server 231 times
and the raw files are committed, so re-running it is a choice, not a default:
notebooks/01_collect.ipynb, or src/collect.py.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("parse_summaries.py", [], "231 Summary PDFs -> one row per agenda item"),
    ("build_dataset.py", [], "classify IT, resolve vendors, publish and record drops"),
    ("validate.py", [], "benchmark against the Comptroller's dataset"),
    ("link_contracts.py", [], "link modifications to awards, roll up by contract"),
    ("analyse.py", [], "the six questions"),
    ("make_figures.py", [], "the six figures, light and dark"),
]


def main():
    for script, extra, description in STEPS:
        print("\n" + "=" * 70)
        print("%s  -  %s" % (script, description))
        print("=" * 70)
        result = subprocess.run([sys.executable, os.path.join(HERE, script)]
                                + extra)
        if result.returncode != 0:
            print("\n%s failed. Stopping - nothing downstream would be "
                  "trustworthy." % script)
            return 1
    print("\nDone. data/final/ and figures/ are rebuilt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
