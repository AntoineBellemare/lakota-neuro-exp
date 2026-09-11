"""Build condition epochs from the cleaned EEG.

    epoch(sub) -> dict[condition -> mne.Epochs]   (saved to derivatives/<sub>/eeg/)

One Epochs object per stimulus condition present in the data (quick_view,
long_view, words). Resting-state (code 11) is a continuous block, not an
event-locked epoch, so it is handled separately by ``resting_segments``.
"""
from __future__ import annotations

from pathlib import Path

from . import config as C
from . import io


def _load_clean_or_raw(sub, verbose=False):
    import mne

    fif = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_desc-clean_raw.fif"
    if fif.exists():
        return mne.io.read_raw_fif(fif, preload=True, verbose=verbose)
    # fall back to raw (unprocessed) if preprocessing hasn't run yet
    return io.load_eeg(sub, verbose=verbose)


def epoch(sub: str, save: bool = True, verbose: bool = False) -> dict:
    import mne

    raw = _load_clean_or_raw(sub, verbose=verbose)
    events = mne.find_events(raw, stim_channel="STI", consecutive=True, verbose=False)

    ecfg = C.CONFIG["epoch"]
    reject = None
    if ecfg.get("reject_uv"):
        reject = {"eeg": ecfg["reject_uv"] * 1e-6}

    out_dir = C.deriv_dir(sub, "eeg")
    epochs = {}
    for cond in ("quick_view", "long_view", "words"):
        code = C.TRIGGERS[cond]
        n_ev = int((events[:, 2] == code).sum())
        if n_ev == 0:
            print(f"[epoch] {sub}: no '{cond}' events (code {code}) — skipped")
            continue
        w = ecfg[cond]
        baseline = tuple(w["baseline"]) if w.get("baseline") else None
        ep = mne.Epochs(
            raw, events, event_id={cond: code},
            tmin=w["tmin"], tmax=w["tmax"], baseline=baseline,
            reject=reject, preload=True, verbose=verbose,
        )
        # median peak-to-peak amplitude across kept epochs (helps set a threshold)
        p2p = ""
        if len(ep):
            import numpy as np
            data = ep.get_data(picks="eeg")           # (n_ep, n_ch, n_t)
            med = float(np.median(data.max(-1) - data.min(-1)) * 1e6)
            p2p = f", median p2p {med:.0f} µV"
        epochs[cond] = ep
        if save:
            fpath = out_dir / f"{sub}_cond-{cond}_epo.fif"
            ep.save(fpath, overwrite=True, verbose=verbose)
            print(f"[epoch] {sub}: {cond} -> {len(ep)}/{n_ev} epochs kept{p2p}  ({fpath.name})")
    return epochs


def resting_segments(sub: str, verbose: bool = False):
    """Return (raw, list-of-(start,stop)-samples) for resting-state blocks.

    RS is tonic: the trigger is held for the whole block. We take each code-11
    onset to the next return-to-zero as one segment.
    """
    import numpy as np

    raw = _load_clean_or_raw(sub, verbose=verbose)
    sti = raw.copy().pick("STI").get_data()[0]
    code = C.TRIGGERS["resting_state"]
    is_rs = sti == code
    edges = np.diff(is_rs.astype(int))
    starts = np.where(edges == 1)[0] + 1
    stops = np.where(edges == -1)[0] + 1
    if is_rs[0]:
        starts = np.r_[0, starts]
    if is_rs[-1]:
        stops = np.r_[stops, len(is_rs)]
    return raw, list(zip(starts.tolist(), stops.tolist()))
