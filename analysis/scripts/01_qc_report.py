"""Sanity check / QC for one or all subjects.

    uv run python analysis/scripts/01_qc_report.py            # all subjects
    uv run python analysis/scripts/01_qc_report.py --sub sub-01
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import qc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n{'='*60}\nQC — {sub}\n{'='*60}")
        report = qc.write_report(sub)
        print(qc._md(report))
        out = report["files"]["paths"].get("source_dir")
        print(f"(full report written under derivatives/{sub}/qc/)")


if __name__ == "__main__":
    main()
