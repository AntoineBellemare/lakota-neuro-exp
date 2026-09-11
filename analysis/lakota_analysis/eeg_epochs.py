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


def _attach_metadata(sub, cond, ep):
    """Attach per-trial condition metadata, aligning for a late EEG start.

    If fewer epochs than behavioral trials, assume the first trials were missed
    (recording started late) and use the trailing trials.
    """
    from . import io

    trials = io.condition_trials(sub, cond)
    n_ep, n_tr = len(ep), len(trials)
    if n_ep == n_tr:
        md = trials
    elif n_ep < n_tr:
        off = n_tr - n_ep
        md = trials.iloc[off:].reset_index(drop=True)
        print(f"[epoch] {sub}: {cond}: {n_ep} epochs vs {n_tr} trials — "
              f"assuming first {off} trial(s) missed (late start); aligned to trailing trials")
    else:
        print(f"[epoch] {sub}: {cond}: more epochs ({n_ep}) than trials ({n_tr}) — metadata skipped")
        return ep
    ep.metadata = md
    return ep


def epoch(sub: str, save: bool = True, verbose: bool = False) -> dict:
    import numpy as np
    import mne

    raw = _load_clean_or_raw(sub, verbose=verbose)
    events = mne.find_events(raw, stim_channel="STI", consecutive=True, verbose=False)

    ecfg = C.CONFIG["epoch"]
    ar_cfg = ecfg.get("autoreject", {})
    use_ar = ar_cfg.get("enabled", False)
    reject = None
    if not use_ar and ecfg.get("reject_uv"):
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
        ep = _attach_metadata(sub, cond, ep)

        note = ""
        if use_ar and len(ep) >= 4:
            ep, note = _run_autoreject(sub, cond, ep, ar_cfg, out_dir, verbose)

        epochs[cond] = ep
        if save:
            fpath = out_dir / f"{sub}_cond-{cond}_epo.fif"
            ep.save(fpath, overwrite=True, verbose=verbose)
            data = ep.get_data(picks="eeg")
            med = float(np.median(data.max(-1) - data.min(-1)) * 1e6) if len(ep) else float("nan")
            print(f"[epoch] {sub}: {cond} -> {len(ep)}/{n_ev} epochs kept, "
                  f"median p2p {med:.0f} µV{note}  ({fpath.name})")
        # short within-stimulus windows for power/complexity
        if C.CONFIG.get("subepoch", {}).get("enabled", False):
            subepochs(sub, cond, save=save, verbose=verbose)
    return epochs


def subepochs(sub: str, cond: str = "long_view", save: bool = True, verbose: bool = False):
    """Cut each stimulus into short fixed-length windows (for power/complexity).

    Windows inherit the parent trial's condition metadata (+ parent_trial, window
    index). Autoreject then operates per-window, so a transient artifact costs one
    short window rather than a whole 5 s trial.
    """
    import numpy as np
    import pandas as pd
    import mne

    from . import io

    sc = C.CONFIG.get("subepoch", {})
    if not sc.get("enabled", False):
        return None

    raw = _load_clean_or_raw(sub, verbose=verbose)
    events = mne.find_events(raw, stim_channel="STI", consecutive=True, verbose=False)
    code = C.TRIGGERS[cond]
    cond_ev = events[events[:, 2] == code]
    if len(cond_ev) == 0:
        return None

    trials = io.condition_trials(sub, cond)
    n_ev, n_tr = len(cond_ev), len(trials)
    if n_ev < n_tr:                                    # late start -> use trailing trials
        trials = trials.iloc[n_tr - n_ev:].reset_index(drop=True)

    sf = raw.info["sfreq"]
    L, ov = sc["length"], sc.get("overlap", 0.0)
    step = L * (1 - ov)
    starts = np.arange(sc.get("tmin", 0.0), sc.get("tmax", 5.0) - L + 1e-9, step)

    sub_ev, md = [], []
    for k in range(n_ev):
        onset = cond_ev[k, 0]
        base = trials.iloc[k].to_dict()
        for wi, st in enumerate(starts):
            sub_ev.append([int(onset + st * sf), 0, code])
            md.append({**base, "parent_trial": k, "window": wi})
    sub_ev = np.array(sub_ev, dtype=int)
    meta = pd.DataFrame(md)

    ep = mne.Epochs(raw, sub_ev, event_id={cond: code}, tmin=0.0, tmax=L,
                    baseline=None, metadata=meta, preload=True, verbose=verbose)

    note = ""
    sc_ar = sc.get("autoreject", True)
    if sc_ar and len(ep) >= 8:
        ar_cfg = C.CONFIG["epoch"].get("autoreject", {})
        ep, note = _run_autoreject(sub, f"{cond}-sub", ep, ar_cfg, C.deriv_dir(sub, "eeg"), verbose)

    if save:
        fpath = C.deriv_dir(sub, "eeg") / f"{sub}_cond-{cond}_desc-sub_epo.fif"
        ep.save(fpath, overwrite=True, verbose=verbose)
        vc = ep.metadata["condition"].value_counts().to_dict()
        print(f"[subepoch] {sub}: {cond} -> {len(ep)} windows "
              f"({L}s, step {step}s){note}; by condition {vc}  ({fpath.name})")
    return ep


def _run_autoreject(sub, cond, ep, ar_cfg, out_dir, verbose):
    """Fit AutoReject, drop/interpolate, and pickle the reject log for QC plots."""
    import pickle

    from autoreject import AutoReject

    n_before = len(ep)
    cv = min(ar_cfg.get("cv", 5), n_before)
    consensus = ar_cfg.get("consensus")
    ar = AutoReject(
        n_interpolate=ar_cfg.get("n_interpolate", [1, 2, 3, 4]),
        consensus=[consensus] if consensus is not None else None,
        cv=cv, random_state=ar_cfg.get("random_state", 97),
        n_jobs=1, verbose=False,
    )
    ep_clean, reject_log = ar.fit_transform(ep, return_log=True)
    with open(out_dir / f"{sub}_cond-{cond}_rejectlog.pkl", "wb") as fh:
        pickle.dump(reject_log, fh)
    n_drop = n_before - len(ep_clean)
    return ep_clean, f"  [autoreject: dropped {n_drop}/{n_before}]"


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
