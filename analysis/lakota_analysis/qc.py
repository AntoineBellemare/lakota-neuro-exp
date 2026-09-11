"""Sanity checks / quality control for one subject.

``run(sub)`` returns a nested dict; ``write_report(sub)`` also writes
``derivatives/<sub>/qc/qc_report.{json,md}``. Nothing here modifies raw data.
"""
from __future__ import annotations

import json
import wave
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from . import io


# ---------------------------------------------------------------------------
def check_files(sub: str) -> dict:
    files = io.find_files(sub)
    present = {k: (v is not None and Path(v).exists()) for k, v in files.items() if k != "source_dir"}
    return {"paths": {k: (str(v) if v else None) for k, v in files.items()}, "present": present}


def check_triggers(sub: str) -> dict:
    """Compare trigger onsets in the EEG against the experiment design."""
    raw = io.load_eeg(sub)
    events = io.load_events(sub, raw)
    codes = events[:, 2]
    counts = {int(k): int(v) for k, v in sorted(Counter(codes.tolist()).items())}

    d = C.DESIGN
    expected = {
        C.TRIGGERS["resting_state"]: d["resting_states"],
        C.TRIGGERS["quick_view"]: d["n_symbols"] * d["quick_reps"],
        C.TRIGGERS["long_view"]: d["n_symbols"] * d["long_reps"],
        C.TRIGGERS["words"]: d["n_symbols"] * d["words_reps"],
    }
    sfreq = raw.info["sfreq"]
    per_code = {}
    for code, exp in expected.items():
        got = counts.get(code, 0)
        per_code[C.TRIGGERS_INV.get(code, str(code))] = {
            "code": code,
            "found": got,
            "expected": exp,
            "missing": exp - got,
            "complete": got == exp,
        }
    onsets = [
        {"t_sec": round(ev[0] / sfreq, 3), "code": int(ev[2]),
         "label": C.TRIGGERS_INV.get(int(ev[2]), str(int(ev[2])))}
        for ev in events
    ]
    return {
        "sfreq": float(sfreq),
        "duration_sec": round(raw.n_times / sfreq, 1),
        "n_channels_eeg": len(raw.copy().pick("eeg").ch_names),
        "counts_raw": counts,
        "per_code": per_code,
        "first_trigger_t_sec": onsets[0]["t_sec"] if onsets else None,
        "onsets": onsets,
    }


def check_behavior(sub: str) -> dict:
    df = io.load_behavior(sub)

    def nonempty(col):
        if col not in df.columns:
            return 0
        s = df[col]
        return int(((~s.isna()) & (s.astype(str).str.strip().ne("")) & (s.astype(str) != "None")).sum())

    d = C.DESIGN
    n = d["n_symbols"]
    checks = {
        "familiarity_ratings": {"found": nonempty("slider.response"), "expected": n * d["long_reps"]},
        "typed_words":         {"found": nonempty("textbox.text"),    "expected": n * d["words_reps"]},
        "mic_clips_referenced":{"found": nonempty("mic.clip"),        "expected": n * d["words_reps"]},
    }
    for v in checks.values():
        v["complete"] = v["found"] == v["expected"]
    return {"n_rows": int(len(df)), "checks": checks}


def _wav_stats(path: Path) -> dict:
    with wave.open(str(path), "rb") as f:
        sw, n, fr, ch = f.getsampwidth(), f.getnframes(), f.getframerate(), f.getnchannels()
        raw = f.readframes(n)
    a = np.frombuffer(raw, dtype={1: np.int8, 2: np.int16, 4: np.int32}[sw]).astype(float)
    full = float(2 ** (sw * 8 - 1))
    peak = float(np.abs(a).max() / full) if a.size else 0.0
    rms = float(np.sqrt((a ** 2).mean()) / full) if a.size else 0.0
    return {"dur_sec": round(n / fr, 1), "sr": fr, "ch": ch,
            "peak_pct": round(100 * peak, 1), "rms_pct": round(100 * rms, 2)}


def check_audio(sub: str, silent_peak_pct: float = 1.0) -> dict:
    files = io.find_files(sub)
    idx = io.audio_index(sub)
    referenced = idx["wav"].dropna().apply(lambda p: Path(p).name).tolist()
    on_disk = sorted(p.name for p in files["mic_dir"].glob("*.wav")) if files["mic_dir"] else []

    per_clip, silent = [], []
    for _, r in idx.iterrows():
        wav = r["wav"]
        if wav and Path(wav).exists():
            st = _wav_stats(Path(wav))
            st.update({"symbol": r["symbol"], "wav": Path(wav).name})
            per_clip.append(st)
            if st["peak_pct"] < silent_peak_pct:
                silent.append(Path(wav).name)

    d = C.DESIGN
    return {
        "expected": d["n_symbols"] * d["words_reps"],
        "referenced_in_csv": len(referenced),
        "on_disk": len(on_disk),
        "extra_on_disk": sorted(set(on_disk) - set(referenced)),
        "missing_on_disk": sorted(set(referenced) - set(on_disk)),
        "silent_clips": silent,
        "per_clip": per_clip,
    }


def run(sub: str) -> dict:
    return {
        "subject": sub,
        "files": check_files(sub),
        "eeg_triggers": check_triggers(sub),
        "behavior": check_behavior(sub),
        "audio": check_audio(sub),
    }


# ---------------------------------------------------------------------------
def _md(report: dict) -> str:
    sub = report["subject"]
    L = [f"# QC report — {sub}", ""]

    L.append("## Files")
    for k, ok in report["files"]["present"].items():
        L.append(f"- {'✅' if ok else '❌'} `{k}`")
    L.append("")

    t = report["eeg_triggers"]
    L += ["## EEG triggers",
          f"- duration **{t['duration_sec']} s** @ {t['sfreq']:.0f} Hz, {t['n_channels_eeg']} EEG channels",
          f"- first trigger at **{t['first_trigger_t_sec']} s**", "",
          "| phase | code | found | expected | status |",
          "|-------|------|-------|----------|--------|"]
    for name, c in t["per_code"].items():
        status = "✅ complete" if c["complete"] else f"⚠️ missing {c['missing']}"
        L.append(f"| {name} | {c['code']} | {c['found']} | {c['expected']} | {status} |")
    L.append("")

    b = report["behavior"]
    L += ["## Behavioral", f"- rows: {b['n_rows']}", "",
          "| response | found | expected | status |", "|---|---|---|---|"]
    for name, c in b["checks"].items():
        L.append(f"| {name} | {c['found']} | {c['expected']} | {'✅' if c['complete'] else '⚠️'} |")
    L.append("")

    a = report["audio"]
    L += ["## Audio (spoken words)",
          f"- expected {a['expected']}, referenced {a['referenced_in_csv']}, on disk {a['on_disk']}",
          f"- extra on disk: {a['extra_on_disk'] or 'none'}",
          f"- missing on disk: {a['missing_on_disk'] or 'none'}",
          f"- silent clips: {a['silent_clips'] or 'none'}", ""]
    return "\n".join(L)


def write_report(sub: str) -> dict:
    report = run(sub)
    out = C.deriv_dir(sub, "qc")
    (out / "qc_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "qc_report.md").write_text(_md(report), encoding="utf-8")
    return report
