"""Speech-to-text for the spoken word-associations (local faster-whisper).

Runs fully offline (after the model is downloaded once), with voice-activity
detection for robustness to background noise / silent gaps.

    transcribe_subject(sub) -> DataFrame  (also writes derivatives/<sub>/audio/)

Notes
-----
* Responses are short word lists, so we keep the raw transcript *and* a naive
  word split; review before using the split for scoring.
* Engine is swappable via config (`stt.engine`); only faster-whisper is wired
  up here.
"""
from __future__ import annotations

import json

import pandas as pd

from . import config as C
from . import io

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    from faster_whisper import WhisperModel

    s = C.CONFIG["stt"]
    device = s.get("device", "auto")
    compute = s.get("compute_type", "int8")
    if device == "auto":
        try:
            import torch  # optional
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
        if device == "cuda":
            compute = "float16"
    print(f"[stt] loading faster-whisper '{s['model']}' on {device} ({compute}) …")
    _MODEL = WhisperModel(s["model"], device=device, compute_type=compute)
    return _MODEL


def transcribe_clip(wav_path) -> dict:
    """Transcribe one wav -> {'text', 'segments', 'language', 'duration', 'vad'}.

    Runs with VAD (robust to noise). If VAD yields no text — quiet or very short
    speech can be swallowed by VAD — it retries once with VAD off so faint clips
    are still recovered.
    """
    s = C.CONFIG["stt"]
    model = _get_model()

    # peak-normalise quiet clips (soft/far speech) -> big robustness win
    audio = str(wav_path)
    if s.get("normalize", True):
        try:
            audio = _load_norm(wav_path, s.get("target_peak", 0.97))
        except Exception as e:
            print(f"[stt] normalize failed for {wav_path} ({e}); using raw file")

    def _run(vad: bool) -> dict:
        segments, info = model.transcribe(
            audio,
            language=s.get("language", "en"),
            vad_filter=vad,
            beam_size=s.get("beam_size", 5),
        )
        segs = [{"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()}
                for seg in segments]
        return {"text": " ".join(x["text"] for x in segs).strip(),
                "segments": segs, "language": info.language,
                "duration": round(info.duration, 1)}

    use_vad = s.get("vad_filter", True)
    res = _run(vad=use_vad)
    res["vad"] = use_vad
    if not res["text"] and use_vad:
        res = _run(vad=False)
        res["vad"] = False  # recovered without VAD
    return res


def transcribe_subject(sub: str, save: bool = True) -> pd.DataFrame:
    idx = io.audio_index(sub)
    out_dir = C.deriv_dir(sub, "audio")
    rows = []
    for i, r in idx.iterrows():
        wav = r["wav"]
        if not (wav and r["wav_exists"]):
            print(f"[stt] {sub}: missing wav for {r['symbol']} — skipped")
            continue
        res = transcribe_clip(wav)
        print(f"[stt] {sub}: {r['symbol']:<24} → {res['text'][:70]!r}")
        n_words = len(_split_words(res["text"]).split(",")) if res["text"] else 0
        review = "" if n_words >= 2 else "REVIEW"  # empty / 1-word = check by ear
        rows.append({
            "symbol": r["symbol"],
            "wav": Path_name(wav),
            "spoken_transcript": res["text"],
            "spoken_words": _split_words(res["text"]),
            "typed_words": r["typed_words"],
            "review": review,
        })
        if save:
            (out_dir / f"{Path_stem(wav)}.json").write_text(
                json.dumps({"symbol": r["symbol"], **res}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    df = pd.DataFrame(rows)
    if save and not df.empty:
        fpath = out_dir / f"{sub}_transcripts.tsv"
        df.to_csv(fpath, sep="\t", index=False)
        print(f"[stt] {sub}: wrote {fpath}")
    return df


# --- small helpers ----------------------------------------------------------
def _load_norm(path, target_peak: float = 0.97):
    """Load wav as mono 16 kHz float32, peak-normalised (Whisper's native rate)."""
    from math import gcd

    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    a, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != 16000:
        g = gcd(int(sr), 16000)
        a = resample_poly(a, 16000 // g, sr // g).astype("float32")
    peak = float(np.abs(a).max()) or 1.0
    return (a * (target_peak / peak)).astype("float32")


def _split_words(text: str) -> str:
    import re
    words = [w for w in re.split(r"[\s,;/]+", text.strip()) if w]
    return ", ".join(words)


def Path_name(p):
    from pathlib import Path
    return Path(p).name


def Path_stem(p):
    from pathlib import Path
    return Path(p).stem
