"""EEG preprocessing: notch, band-pass, bad-channel handling, ICA blink removal.

    preprocess(sub) -> mne.io.Raw   (also saved to derivatives/<sub>/eeg/)

Deliberately conservative and transparent so it's a base for future analyses.
Swap in autoreject / RANSAC / ASR later where marked.
"""
from __future__ import annotations

from . import config as C
from . import io


def preprocess(sub: str, save: bool = True, verbose: bool = False):
    import mne

    pp = C.CONFIG["preprocess"]
    ecfg = C.CONFIG["eeg"]

    raw = io.load_eeg(sub, verbose=verbose)
    raw.load_data(verbose=verbose)

    # keep the stim channel aside; filter only data channels
    # 1) line noise
    if pp.get("notch", True):
        raw.notch_filter(freqs=[ecfg["mains_freq"]], picks="eeg", verbose=verbose)
    # 2) band-pass
    raw.filter(l_freq=pp["l_freq"], h_freq=pp["h_freq"], picks="eeg", verbose=verbose)

    # 3) bad channels (from config; extend with autoreject/RANSAC later)
    bads = (pp.get("bad_channels") or {}).get(sub, [])
    raw.info["bads"] = list(bads)
    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=True, verbose=verbose)

    # 4) ICA to remove eye blinks (frontal channels as EOG proxies)
    ica_info = {"applied": False}
    icfg = pp.get("ica", {})
    if icfg.get("enabled", True):
        method = icfg.get("method", "infomax")
        fit_params = dict(extended=True) if method == "infomax" else None
        ica = mne.preprocessing.ICA(
            n_components=icfg.get("n_components", 0.99),
            method=method,
            fit_params=fit_params,
            random_state=icfg.get("random_state", 97),
            max_iter="auto",
        )
        # fit on a 1 Hz high-passed copy (recommended for stable ICA)
        raw_hp = raw.copy().filter(l_freq=1.0, h_freq=None, picks="eeg", verbose=verbose)
        ica.fit(raw_hp, picks="eeg", verbose=verbose)

        exclude = []
        thr = icfg.get("eog_threshold", 2.5)
        for ch in icfg.get("eog_proxies", ["Fp1", "Fp2"]):
            if ch in raw.ch_names:
                try:
                    idx, _ = ica.find_bads_eog(raw, ch_name=ch, threshold=thr, verbose=verbose)
                    exclude += idx
                except Exception:
                    pass
        ica.exclude = sorted(set(exclude))

        # persist ICA + a topomap so exclusions can be reviewed / overridden
        out = C.deriv_dir(sub, "eeg")
        ica.save(out / f"{sub}_ica.fif", overwrite=True, verbose=verbose)
        try:
            import matplotlib
            matplotlib.use("Agg")
            figs = ica.plot_components(show=False)
            figs = figs if isinstance(figs, list) else [figs]
            for i, fig in enumerate(figs):
                fig.savefig(out / f"{sub}_ica_components{'' if i == 0 else i}.png", dpi=110)
                matplotlib.pyplot.close(fig)
        except Exception as e:
            print(f"[preprocess] {sub}: ICA plot skipped ({e})")

        ica.apply(raw, verbose=verbose)
        ica_info = {"applied": True, "n_components": int(ica.n_components_),
                    "excluded": ica.exclude, "eog_threshold": thr}

    raw.info["description"] = f"lakota {sub} | notch{ecfg['mains_freq']} bp{pp['l_freq']}-{pp['h_freq']} | ICA {ica_info}"

    if save:
        out = C.deriv_dir(sub, "eeg")
        fpath = out / f"{sub}_desc-clean_raw.fif"
        raw.save(fpath, overwrite=True, verbose=verbose)
        print(f"[preprocess] {sub}: saved {fpath}")
        print(f"[preprocess] {sub}: ICA -> {ica_info}")
    return raw
