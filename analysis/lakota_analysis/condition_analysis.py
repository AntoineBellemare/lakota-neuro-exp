"""Meaningful (Lakota / authentic) vs meaningless (invented) — first-pass contrast.

Uses the long-view epochs (5 s, code 13), which carry per-trial condition
metadata. Computes and plots:

    * spectral power  — PSD + relative band power per condition
    * complexity      — spectral entropy, Lempel-Ziv, permutation entropy

    generate(sub) -> figures + tables under derivatives/<sub>/conditions/

⚠️ Single subject, ~7 epochs/condition: treat as EXPLORATORY. The Mann-Whitney
p-values are uncorrected, across-trial (not across-subject), and shown only as a
rough guide — not confirmatory statistics.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from . import viz

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))  # numpy 2.x renamed trapz

COND_COLORS = {"meaningful": "#2a9d8f", "meaningless": "#e76f51"}
BANDS = {"delta": (1, 4), "theta": (4, 8), "alpha": (8, 13),
         "beta": (13, 30), "gamma": (30, 40)}
ORDER = ["meaningful", "meaningless"]


def _load(sub, cond="long_view", kind="sub"):
    """kind='sub' -> short within-stimulus windows; 'trial' -> full 5 s epochs."""
    import mne

    suffix = "_desc-sub" if kind == "sub" else ""
    f = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_cond-{cond}{suffix}_epo.fif"
    if not f.exists() and kind == "sub":
        f = C.paths.derivatives_dir / sub / "eeg" / f"{sub}_cond-{cond}_epo.fif"
    ep = mne.read_epochs(f, verbose=False)
    if ep.metadata is None or "condition" not in ep.metadata:
        raise RuntimeError(f"{sub} {cond}: epochs have no condition metadata — re-run epoching.")
    return ep


# --- power ------------------------------------------------------------------
def power_table(sub, cond="long_view"):
    """Per-epoch relative band power (channel-averaged), post-stimulus window."""
    ep = _load(sub, cond)
    psd = ep.compute_psd(method="welch", fmin=1, fmax=40, tmin=0, verbose=False)
    data, freqs = psd.get_data(return_freqs=True)      # (n_ep, n_ch, n_freq)
    data = data.mean(axis=1)                            # channel-average -> (n_ep, n_freq)
    total = _trapz(data, freqs, axis=1)
    rows = []
    md = ep.metadata.reset_index(drop=True)
    cond_lab = md["condition"].to_numpy()
    for i in range(data.shape[0]):
        row = {"condition": cond_lab[i], "image": md["image"].iloc[i],
               "parent_trial": int(md["parent_trial"].iloc[i]) if "parent_trial" in md else i}
        for band, (lo, hi) in BANDS.items():
            m = (freqs >= lo) & (freqs < hi)
            row[band] = float(_trapz(data[i, m], freqs[m]) / total[i])  # relative
        rows.append(row)
    return pd.DataFrame(rows), (data, freqs, cond_lab)


# --- complexity -------------------------------------------------------------
def complexity_table(sub, cond="long_view"):
    """Per-epoch complexity (channel-averaged) on the post-stimulus window."""
    import antropy as ant

    ep = _load(sub, cond)
    sf = ep.info["sfreq"]
    X = ep.get_data(picks="eeg")                        # (n_ep, n_ch, n_t)
    md = ep.metadata.reset_index(drop=True)
    cond_lab = md["condition"].to_numpy()
    rows = []
    for i in range(X.shape[0]):
        se, lz, pe = [], [], []
        for ch in range(X.shape[1]):
            x = X[i, ch]
            se.append(ant.spectral_entropy(x, sf=sf, method="welch", normalize=True))
            lz.append(ant.lziv_complexity((x > np.median(x)).astype(int), normalize=True))
            pe.append(ant.perm_entropy(x, normalize=True))
        rows.append({"condition": cond_lab[i],
                     "parent_trial": int(md["parent_trial"].iloc[i]) if "parent_trial" in md else i,
                     "spectral_entropy": np.nanmean(se),
                     "lempel_ziv": np.nanmean(lz),
                     "perm_entropy": np.nanmean(pe)})
    return pd.DataFrame(rows)


# --- stats helper -----------------------------------------------------------
def _mwu(df, col):
    """Mann-Whitney on PER-TRIAL means (sub-windows averaged within trial first,
    so pseudo-replication doesn't inflate n). Returns (p, n_meaningful, n_meaningless)."""
    from scipy.stats import mannwhitneyu

    unit = (df.groupby(["condition", "parent_trial"])[col].mean().reset_index()
            if "parent_trial" in df else df)
    a = unit.loc[unit.condition == "meaningful", col].dropna()
    b = unit.loc[unit.condition == "meaningless", col].dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan, len(a), len(b)
    return float(mannwhitneyu(a, b).pvalue), len(a), len(b)


# --- figures ----------------------------------------------------------------
def fig_psd(sub, spec, cond):
    data, freqs, cond_lab = spec
    fig, ax = plt.subplots(figsize=(7.5, 5), constrained_layout=True)
    for c in ORDER:
        d = 10 * np.log10(data[cond_lab == c])          # (n, n_freq) in dB
        m, sem = d.mean(0), d.std(0) / np.sqrt(len(d))
        ax.plot(freqs, m, color=COND_COLORS[c], lw=2, label=f"{c} (n={len(d)})")
        ax.fill_between(freqs, m - sem, m + sem, color=COND_COLORS[c], alpha=0.2)
    ax.set(xlabel="frequency (Hz)", ylabel="power (dB)",
           title=f"{sub} — {cond} PSD by condition (channel-averaged, mean±SEM)")
    ax.legend()
    return fig


def fig_bandpower(sub, tbl, cond):
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    x = np.arange(len(BANDS)); w = 0.36
    for j, c in enumerate(ORDER):
        sub_t = tbl[tbl.condition == c]
        means = [sub_t[b].mean() for b in BANDS]
        sems = [sub_t[b].std() / np.sqrt(len(sub_t)) for b in BANDS]
        ax.bar(x + (j - 0.5) * w, means, w, yerr=sems, capsize=3,
               color=COND_COLORS[c], label=f"{c} (n={len(sub_t)})", alpha=0.9)
        for k, b in enumerate(BANDS):                    # overlay per-epoch points
            xs = np.full(len(sub_t), x[k] + (j - 0.5) * w)
            ax.scatter(xs + np.random.uniform(-0.05, 0.05, len(sub_t)),
                       sub_t[b], color="k", s=8, alpha=0.4, zorder=3)
    for k, b in enumerate(BANDS):
        p, na, nb = _mwu(tbl, b)
        if not np.isnan(p):
            ax.text(x[k], ax.get_ylim()[1] * 0.96, f"p={p:.2f}", ha="center", fontsize=8, color="0.3")
    ntr = _mwu(tbl, list(BANDS)[0])[1:]
    ax.set_xticks(x); ax.set_xticklabels(list(BANDS))
    ax.set(ylabel="relative power",
           title=f"{sub} — {cond} relative band power  (windows; p on {ntr[0]}v{ntr[1]} trials)")
    ax.legend()
    return fig


def fig_complexity(sub, tbl, cond):
    metrics = ["spectral_entropy", "lempel_ziv", "perm_entropy"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), constrained_layout=True)
    for ax, metric in zip(axes, metrics):
        vals = [tbl.loc[tbl.condition == c, metric].dropna().values for c in ORDER]
        bp = ax.boxplot(vals, widths=0.5, patch_artist=True, showmeans=True)
        ax.set_xticks([1, 2]); ax.set_xticklabels(ORDER)
        for patch, c in zip(bp["boxes"], ORDER):
            patch.set_facecolor(COND_COLORS[c]); patch.set_alpha(0.35)
        for j, c in enumerate(ORDER):
            v = tbl.loc[tbl.condition == c, metric].dropna()
            ax.scatter(np.full(len(v), j + 1) + np.random.uniform(-0.06, 0.06, len(v)),
                       v, color=COND_COLORS[c], s=18, zorder=3)
        p, na, nb = _mwu(tbl, metric)
        ax.set_title(f"{metric}\np={p:.2f} ({na}v{nb} trials)" if not np.isnan(p) else metric)
        ax.tick_params(axis="x", labelrotation=15)
    fig.suptitle(f"{sub} — {cond} complexity by condition (points = 1 s windows; exploratory)",
                 fontweight="bold")
    return fig


def fig_alpha_topo(sub, cond):
    """Topography of alpha power difference (meaningful − meaningless)."""
    import mne

    ep = _load(sub, cond)
    psd = ep.compute_psd(method="welch", fmin=1, fmax=40, tmin=0, verbose=False)
    data, freqs = psd.get_data(return_freqs=True)        # (n_ep, n_ch, n_freq)
    lo, hi = BANDS["alpha"]
    m = (freqs >= lo) & (freqs < hi)
    alpha = _trapz(data[:, :, m], freqs[m], axis=2)     # (n_ep, n_ch)
    cl = ep.metadata["condition"].to_numpy()
    diff = alpha[cl == "meaningful"].mean(0) - alpha[cl == "meaningless"].mean(0)
    fig, ax = plt.subplots(figsize=(5, 4.5), constrained_layout=True)
    mne.viz.plot_topomap(diff, ep.copy().pick("eeg").info, axes=ax, show=False, cmap="RdBu_r",
                         contours=4)
    ax.set_title(f"{sub} — alpha power Δ (meaningful − meaningless)")
    return fig


# --- driver -----------------------------------------------------------------
def generate(sub, cond="long_view"):
    viz.set_paper_style()
    out = C.deriv_dir(sub, "conditions")

    ptbl, spec = power_table(sub, cond)
    ctbl = complexity_table(sub, cond)
    ptbl.to_csv(out / f"{sub}_{cond}_bandpower.tsv", sep="\t", index=False)
    ctbl.to_csv(out / f"{sub}_{cond}_complexity.tsv", sep="\t", index=False)

    figs = {
        f"{sub}_{cond}_power_psd": fig_psd(sub, spec, cond),
        f"{sub}_{cond}_power_bands": fig_bandpower(sub, ptbl, cond),
        f"{sub}_{cond}_complexity": fig_complexity(sub, ctbl, cond),
        f"{sub}_{cond}_alpha_topo_diff": fig_alpha_topo(sub, cond),
    }
    saved = []
    for name, fig in figs.items():
        p = out / f"{name}.png"
        fig.savefig(p, bbox_inches="tight")
        plt.close(fig)
        saved.append(p)
        print(f"[cond] {sub}: {name}")
    print(f"[cond] {sub}: n = " +
          ", ".join(f"{c} {int((ptbl.condition == c).sum())}" for c in ORDER))
    return saved
