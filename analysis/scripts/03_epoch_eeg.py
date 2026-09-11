"""Epoch the cleaned EEG per condition and save -epo.fif files.

    uv run python analysis/scripts/03_epoch_eeg.py --sub sub-01
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import eeg_epochs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== epoch {sub} ===")
        eeg_epochs.epoch(sub, save=True)


if __name__ == "__main__":
    main()
