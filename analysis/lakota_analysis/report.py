"""Integrated, self-contained HTML preprocessing report for one subject.

Pulls the QC numbers (fresh) + every figure already produced by steps 01–06 into
a single HTML file with images embedded as base64 (opens in any browser, no server,
nothing external).

    generate(sub) -> derivatives/<sub>/<sub>_report.html
"""
from __future__ import annotations

import base64
import datetime as _dt
from pathlib import Path

import pandas as pd

from . import config as C
from . import qc

# section -> [(relative figure path template, caption), ...]
_SECTIONS = [
    ("Triggers & timeline", [
        ("figures/{s}_03_trigger_timeline.png",
         "Events over the recording. The pink band is the missing start (first RS + quick-view phase)."),
    ]),
    ("Spectra & channels", [
        ("figures/{s}_01_psd_raw_vs_clean.png", "PSD raw vs cleaned (notch 60 Hz + 1–40 Hz + ICA)."),
        ("figures/{s}_02_psd_topomap_bands.png", "Band-power topography (cleaned)."),
        ("figures/{s}_06_channel_psd_heatmap.png", "Per-channel PSD — spot noisy / flat channels."),
        ("figures/{s}_09_bad_channels.png", "Channel amplitude; channels flagged bad in red."),
        ("figures/{s}_10_interpolation.png", "Bad channel(s): signal before vs after interpolation."),
    ]),
    ("ICA", [
        ("figures/{s}_04_ica_components.png", "ICA component topographies (excluded components marked)."),
        ("figures/{s}_05_ica_blink_overlay.png", "Frontal channels before vs after ICA (blink removal)."),
    ]),
    ("Epoching & rejection", [
        ("figures/{s}_11_epoch_rejection.png", "Channel×epoch peak-to-peak with candidate reject thresholds."),
        ("figures/{s}_12_autoreject_log.png", "Autoreject decisions — long-view (green good / blue interpolated / red dropped)."),
        ("figures/{s}_12_autoreject_log_1.png", "Autoreject decisions — words."),
    ]),
    ("Evoked (long-view)", [
        ("figures/{s}_07_evoked_longview.png", "Long-view evoked (butterfly + GFP + scalp maps)."),
        ("figures/{s}_08_epochs_image_longview.png", "Long-view epochs image (GFP per trial)."),
    ]),
    ("Meaningful vs meaningless (long-view)", [
        ("conditions/{s}_long_view_power_psd.png", "PSD by condition (channel-averaged, mean±SEM)."),
        ("conditions/{s}_long_view_power_bands.png", "Relative band power (1 s windows; p on per-trial means)."),
        ("conditions/{s}_long_view_complexity.png", "Complexity: spectral entropy, Lempel-Ziv, permutation entropy."),
        ("conditions/{s}_long_view_alpha_topo_diff.png", "Alpha power Δ (meaningful − meaningless)."),
    ]),
]


def _img(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/png;base64,{b64}" alt="{path.name}">'


def _table(headers, rows) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def _ok(flag: bool) -> str:
    return '<span class="ok">✔</span>' if flag else '<span class="warn">⚠</span>'


def _qc_tables(rep: dict) -> str:
    t = rep["eeg_triggers"]
    trig = _table(
        ["phase", "code", "found", "expected", "status"],
        [[n, c["code"], c["found"], c["expected"],
          _ok(c["complete"]) + ("" if c["complete"] else f' missing {c["missing"]}')]
         for n, c in t["per_code"].items()])

    b = rep["behavior"]["checks"]
    beh = _table(["response", "found", "expected", ""],
                 [[k, v["found"], v["expected"], _ok(v["complete"])] for k, v in b.items()])

    a = rep["audio"]
    aud = _table(["metric", "value"],
                 [["expected", a["expected"]], ["on disk", a["on_disk"]],
                  ["silent clips", len(a["silent_clips"])],
                  ["extra / missing", f'{len(a["extra_on_disk"])} / {len(a["missing_on_disk"])}']])

    return (f"<h3>EEG triggers <span class='muted'>({t['duration_sec']} s @ {t['sfreq']:.0f} Hz, "
            f"{t['n_channels_eeg']} EEG ch; first trigger {t['first_trigger_t_sec']} s)</span></h3>{trig}"
            f"<h3>Behavioral</h3>{beh}<h3>Audio (spoken words)</h3>{aud}")


def _condition_summary(sub) -> str:
    f = C.paths.derivatives_dir / sub / "conditions" / f"{sub}_long_view_bandpower.tsv"
    if not f.exists():
        return ""
    df = pd.read_csv(f, sep="\t")
    rows = []
    for c in ("meaningful", "meaningless"):
        sub_df = df[df.condition == c]
        n_tr = sub_df["parent_trial"].nunique() if "parent_trial" in sub_df else "?"
        rows.append([c, len(sub_df), n_tr])
    return "<h3>Condition units (long-view)</h3>" + _table(["condition", "windows", "trials"], rows)


def _params() -> str:
    pp, ep = C.CONFIG["preprocess"], C.CONFIG["epoch"]
    se = C.CONFIG.get("subepoch", {})
    items = [
        ("Filter", f"notch {C.CONFIG['eeg']['mains_freq']} Hz, band-pass {pp['l_freq']}–{pp['h_freq']} Hz"),
        ("ICA", f"{pp['ica'].get('method','infomax')}, exclude via {pp['ica'].get('eog_proxies')}"),
        ("Epoch rejection", "autoreject" if ep.get("autoreject", {}).get("enabled") else f"p2p {ep.get('reject_uv')} µV"),
        ("Sub-epochs", f"{se.get('length')} s, overlap {se.get('overlap')}" if se.get("enabled") else "off"),
    ]
    return _table(["step", "setting"], items)


CSS = """
:root{color-scheme:light dark}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;max-width:1000px;margin:0 auto;
     padding:2rem 1.2rem;line-height:1.5;color:#1a1a1a;background:#fafafa}
h1{color:#3d1c5c;border-bottom:3px solid #5b2a86;padding-bottom:.2em;margin-bottom:.1em}
h2{color:#3d1c5c;border-bottom:1px solid #ddd;padding-bottom:.15em;margin-top:2.2rem}
h3{color:#444;margin:1.1rem 0 .3rem}
.muted,.sub{color:#777;font-weight:normal;font-size:.85em}
table{border-collapse:collapse;margin:.4rem 0 1rem;font-size:.9rem}
th,td{border:1px solid #ccc;padding:.25rem .6rem;text-align:left}
th{background:#efe9f4}
.ok{color:#2a9d8f;font-weight:bold}.warn{color:#e76f51;font-weight:bold}
figure{margin:1.2rem 0}
img{max-width:100%;border:1px solid #ddd;border-radius:6px;background:#fff}
figcaption{color:#555;font-size:.85rem;margin-top:.3rem}
.toc a{display:inline-block;margin:.15rem .6rem .15rem 0;color:#5b2a86;text-decoration:none}
footer{margin-top:3rem;color:#999;font-size:.8rem;border-top:1px solid #eee;padding-top:1rem}
"""


def generate(sub: str) -> Path:
    rep = qc.run(sub)                                    # fresh QC numbers
    deriv = C.paths.derivatives_dir / sub
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [f"<h1>Preprocessing report — {sub}</h1>",
             f"<div class='sub'>Lakota Neuro · generated {now}</div>"]

    # table of contents
    parts.append("<div class='toc'>" + " ".join(
        f"<a href='#s{i}'>{name}</a>" for i, (name, _) in enumerate(_SECTIONS)) + "</div>")

    # overview
    parts.append("<h2>Overview</h2>")
    parts.append(_params())
    parts.append(_qc_tables(rep))
    parts.append(_condition_summary(sub))

    # figure sections
    for i, (name, figs) in enumerate(_SECTIONS):
        parts.append(f"<h2 id='s{i}'>{name}</h2>")
        any_fig = False
        for tmpl, cap in figs:
            path = deriv / tmpl.format(s=sub)
            if path.exists():
                any_fig = True
                parts.append(f"<figure>{_img(path)}<figcaption>{cap}</figcaption></figure>")
        if not any_fig:
            parts.append("<p class='muted'>(no figures — run the relevant step)</p>")

    parts.append("<footer>Self-contained (images embedded). Regenerate with "
                 "<code>07_report.py</code> after re-running the pipeline.</footer>")

    html = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{sub} preprocessing report</title><style>{CSS}</style></head>"
            f"<body>{''.join(parts)}</body></html>")

    out = deriv / f"{sub}_report.html"
    out.write_text(html, encoding="utf-8")
    print(f"[report] {sub}: wrote {out}  ({out.stat().st_size/1e6:.1f} MB)")
    return out
