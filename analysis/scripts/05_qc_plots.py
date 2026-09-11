"""Generate paper-ready sanity-check figures (PSD, triggers, ICA, evoked).

    uv run python analysis/scripts/05_qc_plots.py --sub sub-01

Outputs PNGs (300 dpi) + a combined PDF under derivatives/<sub>/figures/.
Requires 02_preprocess_eeg.py (cleaned raw + ICA) and 03_epoch_eeg.py first.
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import viz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== figures {sub} ===")
        saved = viz.generate_all(sub)
        print(f"[viz] {sub}: wrote {len(saved)} files under derivatives/{sub}/figures/")


if __name__ == "__main__":
    main()
