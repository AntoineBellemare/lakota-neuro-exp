"""First-pass meaningful vs meaningless contrast (power + complexity, long window).

    uv run python analysis/scripts/06_condition_analysis.py --sub sub-01

Requires 02_preprocess_eeg.py + 03_epoch_eeg.py (epochs carry condition metadata).
Outputs figures + tables under derivatives/<sub>/conditions/.
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import condition_analysis as ca


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    ap.add_argument("--cond", default="long_view", help="condition/phase (default: long_view)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== condition analysis {sub} ({args.cond}) ===")
        ca.generate(sub, cond=args.cond)


if __name__ == "__main__":
    main()
