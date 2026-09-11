"""Locate and load a subject's raw data.

The raw folder (e.g. ``data/pilot-01``) contains files with long PsychoPy /
DSI names; we discover them by pattern so nothing is hard-coded per subject.

    find_files(sub)      -> dict of resolved paths
    load_eeg(sub)        -> mne.io.RawArray (EEG + 'Trigger' stim channel)
    load_behavior(sub)   -> pandas.DataFrame (PsychoPy trial-by-trial csv)
    audio_index(sub)     -> DataFrame: symbol, wav_path, typed_words
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

# DSI-Streamer CSV has 13 header/comment lines before the column row.
_DSI_HEADER_LINES = 13


# ---------------------------------------------------------------------------
# file discovery
# ---------------------------------------------------------------------------
def find_files(sub: str) -> dict[str, Path | None]:
    """Discover the raw files for a subject by filename pattern."""
    d = C.source_dir(sub)
    if not d.exists():
        raise FileNotFoundError(f"Source dir not found: {d}")

    def one(pattern: str, exclude: str | None = None) -> Path | None:
        hits = [Path(p) for p in glob.glob(str(d / pattern))]
        if exclude:
            hits = [p for p in hits if exclude not in p.name]
        return sorted(hits)[0] if hits else None

    eeg_csv = one("*_M_raw.csv")
    eeg_edf = one("*_M_raw.edf")
    # behavioral PsychoPy csv = the lakota csv that is NOT the EEG export
    beh_csv = one("*lakota_symbols*.csv", exclude="_M_raw")
    psydat = one("*lakota_symbols*.psydat")
    mic_dirs = [Path(p) for p in glob.glob(str(d / "*_mic_recorded")) if Path(p).is_dir()]
    mic_dir = sorted(mic_dirs)[0] if mic_dirs else None

    return {
        "source_dir": d,
        "eeg_csv": eeg_csv,
        "eeg_edf": eeg_edf,
        "behavior_csv": beh_csv,
        "psydat": psydat,
        "mic_dir": mic_dir,
    }


# ---------------------------------------------------------------------------
# EEG
# ---------------------------------------------------------------------------
def load_eeg(sub: str, verbose: bool = False):
    """Load the DSI-24 EEG CSV into an MNE Raw object.

    Scalp channels are EEG, the two ear references (A1/A2) are 'misc', and the
    DSI 'Trigger' column becomes a 'stim' channel named ``STI`` so that
    :func:`mne.find_events` works directly.
    """
    import mne

    files = find_files(sub)
    if files["eeg_csv"] is None:
        raise FileNotFoundError(f"No *_M_raw.csv EEG file for {sub}")

    ecfg = C.CONFIG["eeg"]
    ch_names = list(ecfg["channels"])
    cols = [f"{c}-Vref" for c in ch_names] + ["Trigger"]
    df = pd.read_csv(files["eeg_csv"], skiprows=_DSI_HEADER_LINES, usecols=cols)

    eeg = df[[f"{c}-Vref" for c in ch_names]].to_numpy().T * float(ecfg["eeg_units_to_volts"])
    trig = df["Trigger"].to_numpy(dtype=float)[np.newaxis, :]
    data = np.vstack([eeg, trig])

    refs = set(ecfg["reference_channels"])
    ch_types = ["misc" if c in refs else "eeg" for c in ch_names] + ["stim"]
    info = mne.create_info(ch_names + ["STI"], sfreq=float(ecfg["sfreq"]), ch_types=ch_types)
    raw = mne.io.RawArray(data, info, verbose=verbose)

    # rename old 10-20 labels and attach the standard montage
    raw.rename_channels(ecfg.get("rename_for_montage", {}))
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", match_case=False, verbose=verbose)
    return raw


def load_events(sub, raw=None):
    """Return the MNE events array (n, 3) from the Trigger stim channel."""
    import mne

    if raw is None:
        raw = load_eeg(sub)
    return mne.find_events(raw, stim_channel="STI", consecutive=True, verbose=False)


# ---------------------------------------------------------------------------
# behavior + audio
# ---------------------------------------------------------------------------
def load_behavior(sub: str) -> pd.DataFrame:
    """Load the PsychoPy trial-by-trial CSV (utf-8-sig handles the BOM)."""
    files = find_files(sub)
    if files["behavior_csv"] is None:
        raise FileNotFoundError(f"No behavioral CSV for {sub}")
    return pd.read_csv(files["behavior_csv"], encoding="utf-8-sig")


# condition (meaningful/meaningless) trial tables ---------------------------
# which PsychoPy loop corresponds to each trigger condition
_LOOP_OF = {"quick_view": "trials", "long_view": "trials_3", "words": "trials_2"}


def condition_trials(sub: str, cond: str) -> pd.DataFrame:
    """Ordered trial table for one phase: image, category, meaningful, condition.

    Rows are in presentation order (as recorded). 'meaningful' is True when the
    stimulus category is the configured meaningful category ('authentic').
    """
    df = load_behavior(sub)
    loop = _LOOP_OF[cond]
    key = f"{loop}.thisN"
    if key not in df.columns:
        raise KeyError(f"No loop column {key!r} in behavior for {cond}")
    mask = pd.to_numeric(df[key], errors="coerce").notna()
    t = df[mask].reset_index(drop=True)

    mean_cat = str(C.CONFIG.get("conditions", {}).get("meaningful_category", "authentic")).lower()
    cat = t["category"].astype(str)
    out = pd.DataFrame({"image": t["image"].values, "category": cat.values})
    out["meaningful"] = cat.str.lower().eq(mean_cat).values
    out["condition"] = np.where(out["meaningful"], "meaningful", "meaningless")
    if "slider.response" in t:
        out["familiarity"] = pd.to_numeric(t["slider.response"], errors="coerce").values
    if "textbox.text" in t:
        out["typed_words"] = t["textbox.text"].values
    return out


def audio_index(sub: str) -> pd.DataFrame:
    """One row per spoken-word clip: symbol, resolved wav path, typed words.

    Rows are the trials that reference a ``mic.clip`` (the words phase).
    """
    files = find_files(sub)
    df = load_behavior(sub)
    rows = []
    for _, r in df.iterrows():
        clip = r.get("mic.clip")
        if pd.isna(clip) or str(clip) in ("", "None"):
            continue
        name = Path(str(clip).replace("\\", "/")).name
        wav = (files["mic_dir"] / name) if files["mic_dir"] else None
        rows.append(
            {
                "symbol": r.get("image"),
                "wav": wav,
                "wav_exists": bool(wav and wav.exists()),
                "typed_words": r.get("textbox.text"),
            }
        )
    return pd.DataFrame(rows)
