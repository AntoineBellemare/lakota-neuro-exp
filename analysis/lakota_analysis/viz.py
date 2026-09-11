"""Paper-ready sanity-check figures for one subject.

    generate_all(sub) -> writes PNGs (300 dpi) + a combined PDF to
                         derivatives/<sub>/figures/

Figures
-------
1  PSD, raw vs cleaned        (line-noise + band-pass + ICA effect)
2  PSD topomaps by band        (delta/theta/alpha/beta, cleaned)
3  Trigger timeline            (events over time; highlights the missing start)
4  ICA component topographies  (what ICA decomposed)
5  ICA before/after on blinks  (blink-locked overlay — the cleaning it did)
6  Per-channel PSD heatmap      (spot noisy / flat channels)
7  Long-view evoked (joint)     (butterfly + GFP + scalp maps)
8  Long-view epochs image       (single-trial GFP)

Everything is wrapped in try/except so one failing panel never sinks the suite.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from . import config as C
from . import io

_BANDS = {"Delta (1-4 Hz)": (1, 4), "Theta (4-8 Hz)": (4, 8),
          "Alpha (8-13 Hz)": (8, 13), "Beta (13-30 Hz)": (13, 30)}


def set_paper_style():
    plt.rcParams.update({
        "figure.dpi": 120, "savefig.dpi": 300, "figure.facecolor": "white",
        "savefig.facecolor": "white", "font.family": "sans-serif",
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "legend.frameon": False,
    })


# --- data loaders -----------------------------------------------------------
def _raw_and_clean(sub):
    """Return (raw_unfiltered, raw_cleaned) — both with the stim channel dropped."""
    import mne

    raw = io.load_eeg(sub)
    raw.load_data()
    clean_fif = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_desc-clean_raw.fif"
    clean = mne.io.read_raw_fif(clean_fif, preload=True, verbose=False) if clean_fif.exists() else None
    return raw.pick("eeg"), (clean.pick("eeg") if clean else None)


# --- individual figures -----------------------------------------------------
def fig_psd_raw_clean(sub, raw, clean):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for ax, inst, title in [(axes[0], raw, "Raw"), (axes[1], clean, "Cleaned (notch + 1–40 Hz + ICA)")]:
        if inst is None:
            ax.set_visible(False)
            continue
        psd = inst.compute_psd(method="welch", fmin=1, fmax=80, verbose=False)
        psd.plot(axes=ax, show=False, spatial_colors=True, amplitude=False)
        ax.set_title(title)
        ax.axvline(C.CONFIG["eeg"]["mains_freq"], color="grey", ls=":", lw=1)
    fig.suptitle(f"{sub} — power spectral density", fontweight="bold")
    return fig


def fig_psd_topo(sub, clean):
    psd = clean.compute_psd(method="welch", fmin=1, fmax=40, verbose=False)
    fig = psd.plot_topomap(bands=_BANDS, normalize=True, show=False)
    fig.suptitle(f"{sub} — band power topography (normalised)", fontweight="bold")
    return fig


def fig_trigger_timeline(sub):
    raw = io.load_eeg(sub)
    events = io.load_events(sub, raw)
    sf = raw.info["sfreq"]
    t = events[:, 0] / sf
    codes = events[:, 2]
    labels = list(C.TRIGGERS.keys())            # ordered resting/quick/long/words
    code_of = C.TRIGGERS
    ypos = {code_of[l]: i for i, l in enumerate(labels)}
    colors = dict(zip(labels, plt.cm.viridis(np.linspace(0.05, 0.85, len(labels)))))

    fig, ax = plt.subplots(figsize=(11, 3.2), constrained_layout=True)
    dur = raw.n_times / sf
    first = t.min() if len(t) else 0
    ax.axvspan(0, first, color="crimson", alpha=0.08)
    ax.text(first / 2, len(labels) - 0.5, "no triggers\n(recording gap)",
            ha="center", va="top", fontsize=8, color="crimson")
    for code, y in ypos.items():
        m = codes == code
        lab = C.TRIGGERS_INV[code]
        ax.scatter(t[m], np.full(m.sum(), y), marker="|", s=350,
                   color=colors[lab], label=f"{lab} ({code}) ×{int(m.sum())}")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels([f"{l} ({code_of[l]})" for l in labels])
    ax.set_xlabel("time (s)")
    ax.set_xlim(0, dur)
    ax.set_title(f"{sub} — trigger timeline  ({dur:.0f} s recording)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    ax.grid(axis="x", alpha=0.25)
    ax.grid(axis="y", alpha=0)
    return fig


def fig_ica_components(sub):
    import mne

    ica = mne.preprocessing.read_ica(C.paths.derivatives_dir / sub / "eeg" / f"{sub}_ica.fif")
    figs = ica.plot_components(show=False, title=f"{sub} — ICA components (excluded: {ica.exclude})")
    return figs if isinstance(figs, list) else [figs]


def fig_ica_overlay(sub, raw_filtered):
    """Before/after ICA — blink-locked ERP if blinks are found, else a time segment."""
    import mne

    ica = mne.preprocessing.read_ica(C.paths.derivatives_dir / sub / "eeg" / f"{sub}_ica.fif")

    # 1) preferred: blink-locked ERP overlay
    for ch in C.CONFIG["preprocess"]["ica"].get("eog_proxies", ["Fp1", "Fp2"]):
        if ch in raw_filtered.ch_names:
            try:
                eog_ep = mne.preprocessing.create_eog_epochs(raw_filtered, ch_name=ch, verbose=False)
                if len(eog_ep) >= 3:
                    fig = ica.plot_overlay(eog_ep.average(), exclude=ica.exclude, show=False)
                    fig.suptitle(f"{sub} — blink-locked ERP before/after ICA (ch {ch}, n={len(eog_ep)})",
                                 fontweight="bold")
                    return fig
            except Exception:
                continue

    # 2) fallback: overlay a raw time segment of frontal channels before/after ICA
    picks = [c for c in ["Fp1", "Fp2", "F3", "F4", "Fz"] if c in raw_filtered.ch_names]
    after = ica.apply(raw_filtered.copy(), exclude=ica.exclude, verbose=False)
    t0 = min(30.0, raw_filtered.times[-1] * 0.2)
    dur = 15.0
    sf = raw_filtered.info["sfreq"]
    sl = slice(int(t0 * sf), int((t0 + dur) * sf))
    times = raw_filtered.times[sl]
    b = raw_filtered.get_data(picks=picks)[:, sl] * 1e6
    a = after.get_data(picks=picks)[:, sl] * 1e6

    fig, axes = plt.subplots(len(picks), 1, figsize=(11, 1.5 * len(picks)),
                             sharex=True, constrained_layout=True)
    axes = np.atleast_1d(axes)
    for i, ch in enumerate(picks):
        axes[i].plot(times, b[i], color="0.6", lw=0.8, label="before ICA")
        axes[i].plot(times, a[i], color="crimson", lw=0.8, label="after ICA")
        axes[i].set_ylabel(f"{ch}\n(µV)")
        if i == 0:
            axes[i].legend(loc="upper right", ncol=2, fontsize=8)
    axes[-1].set_xlabel("time (s)")
    fig.suptitle(f"{sub} — frontal channels before/after ICA (excluded {ica.exclude})",
                 fontweight="bold")
    return fig


def fig_channel_psd_heatmap(sub, clean):
    psd = clean.compute_psd(method="welch", fmin=1, fmax=40, verbose=False)
    data, freqs = psd.get_data(return_freqs=True)
    db = 10 * np.log10(data)
    fig, ax = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    im = ax.imshow(db, aspect="auto", origin="lower", cmap="magma",
                   extent=[freqs[0], freqs[-1], 0, len(clean.ch_names)])
    ax.set_yticks(np.arange(len(clean.ch_names)) + 0.5)
    ax.set_yticklabels(clean.ch_names, fontsize=7)
    ax.set_xlabel("frequency (Hz)")
    ax.set_title(f"{sub} — per-channel PSD (dB) — spot noisy/flat channels")
    fig.colorbar(im, ax=ax, label="power (dB)")
    return fig


def fig_evoked_joint(sub):
    import mne

    epo = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_cond-long_view_epo.fif"
    if not epo.exists():
        return None
    ev = mne.read_epochs(epo, verbose=False).average()
    fig = ev.plot_joint(title=f"{sub} — long-view evoked (n={ev.nave})", show=False)
    return fig


def fig_epochs_image(sub):
    import mne

    epo = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_cond-long_view_epo.fif"
    if not epo.exists():
        return None
    epochs = mne.read_epochs(epo, verbose=False)
    figs = epochs.plot_image(combine="gfp", show=False,
                             title=f"{sub} — long-view epochs (GFP)")
    return figs if isinstance(figs, list) else [figs]


def _bads(sub):
    return list((C.CONFIG["preprocess"].get("bad_channels") or {}).get(sub, []))


def fig_bad_channels(sub, raw_filt):
    """Per-channel std (band-passed, pre-interpolation); interpolated channels in red."""
    names = raw_filt.copy().pick("eeg").ch_names
    std = raw_filt.get_data(picks="eeg").std(1) * 1e6
    bads = set(_bads(sub))
    order = np.argsort(std)
    y = np.arange(len(names))
    colors = ["crimson" if names[i] in bads else "steelblue" for i in order]
    med = float(np.median(std))

    fig, ax = plt.subplots(figsize=(7, 6), constrained_layout=True)
    ax.barh(y, std[order], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([names[i] for i in order], fontsize=8)
    ax.axvline(med, color="k", ls="--", lw=1, label=f"median {med:.1f} µV")
    ax.axvline(3 * med, color="grey", ls=":", lw=1, label=f"3× median")
    ax.set_xlabel("channel std (µV)")
    ax.set_title(f"{sub} — channel amplitude (bad = red: {sorted(bads) or 'none'})")
    ax.legend(loc="lower right", fontsize=8)
    return fig


def fig_interpolation(sub, raw_filt):
    """Interpolated channels: signal before (bad) vs after interpolation, one segment."""
    bads = _bads(sub)
    picks = [c for c in bads if c in raw_filt.ch_names]
    if not picks:
        return None
    after = raw_filt.copy()
    after.info["bads"] = picks
    after.interpolate_bads(reset_bads=True, verbose=False)

    sf = raw_filt.info["sfreq"]
    t0 = min(30.0, raw_filt.times[-1] * 0.2)
    sl = slice(int(t0 * sf), int((t0 + 15) * sf))
    times = raw_filt.times[sl]
    b = raw_filt.get_data(picks=picks)[:, sl] * 1e6
    a = after.get_data(picks=picks)[:, sl] * 1e6

    fig, axes = plt.subplots(len(picks), 1, figsize=(11, 1.8 * len(picks)),
                             sharex=True, squeeze=False, constrained_layout=True)
    for i, ch in enumerate(picks):
        ax = axes[i, 0]
        ax.plot(times, b[i], color="crimson", lw=0.7, label="before (flagged bad)")
        ax.plot(times, a[i], color="seagreen", lw=0.9, label="after interpolation")
        ax.set_ylabel(f"{ch}\n(µV)")
        if i == 0:
            ax.legend(loc="upper right", ncol=2, fontsize=8)
    axes[-1, 0].set_xlabel("time (s)")
    fig.suptitle(f"{sub} — bad-channel interpolation", fontweight="bold")
    return fig


def fig_autoreject_logs(sub):
    """AutoReject decision grids (good / interpolated / dropped) per condition."""
    import glob
    import pickle

    figs = []
    for pkl in sorted(glob.glob(str(C.paths.derivatives_dir / sub / "eeg" / "*_rejectlog.pkl"))):
        cond = pkl.split("cond-")[-1].split("_rejectlog")[0]
        with open(pkl, "rb") as fh:
            rl = pickle.load(fh)
        rl.plot(orientation="horizontal", show=False)
        fig = plt.gcf()
        fig.suptitle(f"{sub} — autoreject: {cond} (green=good, blue=interpolated, red=dropped)",
                     fontweight="bold", fontsize=10)
        figs.append(fig)
    return figs


def fig_epoch_rejection(sub):
    """Per-epoch × channel peak-to-peak, with candidate reject thresholds."""
    import mne

    conds, data = [], {}
    for cond in ("long_view", "words"):
        f = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_cond-{cond}_epo.fif"
        if f.exists():
            ep = mne.read_epochs(f, verbose=False)
            if len(ep):
                d = ep.get_data(picks="eeg") * 1e6      # (n_ep, n_ch, n_t)
                data[cond] = (ep.copy().pick("eeg").ch_names, d.max(-1) - d.min(-1))
                conds.append(cond)
    if not conds:
        return None

    thresholds = [100, 150, 200]
    fig, axes = plt.subplots(len(conds), 2, figsize=(12, 3.4 * len(conds)),
                             squeeze=False, constrained_layout=True,
                             gridspec_kw={"width_ratios": [2, 1.2]})
    for r, cond in enumerate(conds):
        names, p2p = data[cond]                          # p2p: (n_ep, n_ch)
        im = axes[r, 0].imshow(p2p.T, aspect="auto", origin="lower", cmap="magma",
                               vmax=np.percentile(p2p, 98))
        axes[r, 0].set_yticks(np.arange(len(names)))
        axes[r, 0].set_yticklabels(names, fontsize=6)
        axes[r, 0].set_xlabel("epoch")
        axes[r, 0].set_title(f"{cond}: channel × epoch p2p (µV)")
        fig.colorbar(im, ax=axes[r, 0], label="µV")

        emax = p2p.max(1)                                # worst channel per epoch
        axes[r, 1].plot(np.arange(len(emax)), emax, "o-", ms=3, color="0.3")
        for th in thresholds:
            n_bad = int((emax > th).sum())
            axes[r, 1].axhline(th, ls="--", lw=1,
                               label=f"{th} µV → drop {n_bad}/{len(emax)}")
        axes[r, 1].set_xlabel("epoch")
        axes[r, 1].set_ylabel("max p2p (µV)")
        axes[r, 1].set_title(f"{cond}: worst-channel p2p per epoch")
        axes[r, 1].legend(fontsize=7)
    fig.suptitle(f"{sub} — epoch rejection diagnostics (reject currently OFF)",
                 fontweight="bold")
    return fig


# --- driver -----------------------------------------------------------------
def generate_all(sub: str) -> list:
    set_paper_style()
    out = C.deriv_dir(sub, "figures")
    raw, clean = _raw_and_clean(sub)

    # pre-ICA filtered copy (for the blink overlay)
    raw_filt = raw.copy().notch_filter([C.CONFIG["eeg"]["mains_freq"]], verbose=False)
    raw_filt.filter(C.CONFIG["preprocess"]["l_freq"], C.CONFIG["preprocess"]["h_freq"], verbose=False)

    jobs = [
        ("01_psd_raw_vs_clean", lambda: [fig_psd_raw_clean(sub, raw, clean)]),
        ("02_psd_topomap_bands", lambda: [fig_psd_topo(sub, clean)] if clean else []),
        ("03_trigger_timeline", lambda: [fig_trigger_timeline(sub)]),
        ("04_ica_components", lambda: fig_ica_components(sub)),
        ("05_ica_blink_overlay", lambda: [f for f in [fig_ica_overlay(sub, raw_filt)] if f]),
        ("06_channel_psd_heatmap", lambda: [fig_channel_psd_heatmap(sub, clean)] if clean else []),
        ("07_evoked_longview", lambda: [f for f in [fig_evoked_joint(sub)] if f]),
        ("08_epochs_image_longview", lambda: fig_epochs_image(sub)),
        ("09_bad_channels", lambda: [fig_bad_channels(sub, raw_filt)]),
        ("10_interpolation", lambda: [f for f in [fig_interpolation(sub, raw_filt)] if f]),
        ("11_epoch_rejection", lambda: [f for f in [fig_epoch_rejection(sub)] if f]),
        ("12_autoreject_log", lambda: fig_autoreject_logs(sub)),
    ]

    saved, all_figs = [], []
    for name, fn in jobs:
        try:
            figs = fn() or []
            for i, fig in enumerate(figs):
                suffix = "" if i == 0 else f"_{i}"
                png = out / f"{sub}_{name}{suffix}.png"
                fig.savefig(png, bbox_inches="tight")
                saved.append(png)
                all_figs.append(fig)
            print(f"[viz] {sub}: {name} -> {len(figs)} fig(s)")
        except Exception as e:
            print(f"[viz] {sub}: {name} FAILED ({type(e).__name__}: {e})")

    # combined multi-page PDF
    if all_figs:
        pdf_path = out / f"{sub}_qc_figures.pdf"
        with PdfPages(pdf_path) as pdf:
            for fig in all_figs:
                pdf.savefig(fig, bbox_inches="tight")
        saved.append(pdf_path)
        print(f"[viz] {sub}: combined -> {pdf_path.name}")
    for fig in all_figs:
        plt.close(fig)
    return saved
