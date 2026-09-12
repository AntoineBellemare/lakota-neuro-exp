"""Assemble a self-contained HTML preprocessing report from the derivatives.

    uv run python analysis/scripts/07_report.py --sub sub-01

Run after 01–06 (it embeds whatever figures exist). Output:
derivatives/<sub>/<sub>_report.html — open in any browser.
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== report {sub} ===")
        report.generate(sub)


if __name__ == "__main__":
    main()
