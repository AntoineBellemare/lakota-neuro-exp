"""Preprocess EEG (notch / band-pass / ICA) and save cleaned raw.

    uv run python analysis/scripts/02_preprocess_eeg.py --sub sub-01
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import eeg_preprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== preprocess {sub} ===")
        eeg_preprocess.preprocess(sub, save=True)


if __name__ == "__main__":
    main()
