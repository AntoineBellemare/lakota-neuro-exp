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
