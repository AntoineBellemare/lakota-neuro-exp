"""Transcribe spoken word-associations with local faster-whisper.

    uv run python analysis/scripts/04_transcribe_audio.py --sub sub-01

First run downloads the Whisper model (~0.5 GB for small.en); afterwards it is
fully offline.
"""
import argparse

import _bootstrap  # noqa: F401
from lakota_analysis import subjects
from lakota_analysis import stt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default=None, help="subject label (default: all)")
    args = ap.parse_args()

    for sub in ([args.sub] if args.sub else subjects):
        print(f"\n=== transcribe {sub} ===")
        stt.transcribe_subject(sub, save=True)


if __name__ == "__main__":
    main()
