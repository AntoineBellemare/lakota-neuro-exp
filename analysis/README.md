# Lakota Neuro — analysis

Sanity-check + preprocessing pipeline for the Lakota-symbols EEG + audio
experiment (DSI-24 EEG via a Trigger-Hub, PsychoPy behavior, spoken/typed word
associations). Config-driven and subject-agnostic so it scales as subjects are
added.

## Layout

```
analysis/
├── config.yaml            # ← single source of truth: paths, subjects, params
├── lakota_analysis/       # importable package
│   ├── config.py          #   load config, resolve paths
│   ├── io.py              #   discover + load EEG / behavior / audio
│   ├── qc.py              #   sanity checks → JSON + Markdown report
│   ├── eeg_preprocess.py  #   notch / band-pass / ICA
│   ├── eeg_epochs.py      #   condition epochs from the trigger channel
│   └── stt.py             #   faster-whisper transcription
└── scripts/               # thin CLI runners
    ├── 01_qc_report.py
    ├── 02_preprocess_eeg.py
    ├── 03_epoch_eeg.py
    └── 04_transcribe_audio.py
```

Raw data stays in `data/<source_dir>/` (untouched). All outputs go to
`data/derivatives/<sub>/` (git-ignored):

```
data/derivatives/sub-01/
├── qc/     qc_report.{json,md}
├── eeg/     *_desc-clean_raw.fif, *_ica.fif, *_cond-*_epo.fif
├── audio/   <sub>_transcripts.tsv, <clip>.json
└── figures/ *_01..08_*.png (300 dpi) + <sub>_qc_figures.pdf
```

### QC figures (`05_qc_plots.py`)

1 PSD raw vs cleaned · 2 band-power topomaps · 3 trigger timeline ·
4 ICA components · 5 ICA before/after · 6 per-channel PSD heatmap ·
7 long-view evoked (joint) · 8 long-view epochs image. All also bundled into one
PDF.

## Setup

Dependencies are managed with **uv** (already added to `pyproject.toml`):

```bash
uv sync
```

Key libs: `mne` (EEG), `faster-whisper` (offline speech-to-text), `pandas`,
`pyyaml`, `matplotlib`.

## Run

```bash
# sanity check (all subjects, or --sub sub-01)
uv run python analysis/scripts/01_qc_report.py

# EEG: clean, then epoch
uv run python analysis/scripts/02_preprocess_eeg.py --sub sub-01
uv run python analysis/scripts/03_epoch_eeg.py       --sub sub-01

# audio: transcribe spoken words (first run downloads the Whisper model)
uv run python analysis/scripts/04_transcribe_audio.py --sub sub-01

# paper-ready QC figures (PSD, triggers, ICA, evoked) → figures/ + a combined PDF
uv run python analysis/scripts/05_qc_plots.py --sub sub-01
```

## Adding a subject

Drop the raw folder under `data/`, then add to `config.yaml`:

```yaml
subjects:
  sub-02:
    source_dir: pilot-02
```

Files inside are auto-discovered by pattern (`*_M_raw.csv` EEG, `*lakota_symbols*.csv`
behavior, `*_mic_recorded/` audio) — no per-subject filenames to maintain.

## Trigger codes

| code | phase | epoched |
|------|-------|---------|
| 11 | resting state (start & end) | continuous block (see `eeg_epochs.resting_segments`) |
| 12 | quick view (phase 1, ×2) | yes |
| 13 | long view (phase 2, + rating) | yes |
| 14 | words (phase 3, typed + spoken) | yes |

Triggers are **tonic** (held for the routine, then reset to 0); onsets are the
0→code transitions.

---

## Pilot (`sub-01`) — status & caveats

Run `01_qc_report.py` for the live version; as of the first pass:

- **Behavioral:** 20/20 ratings, **19/20 typed word-lists** (one blank), 20/20 mic refs.
- **Audio:** 20/20 clips present, none silent, all mapped to distinct symbols. ✅
- **EEG:** recording started late — **first RS, the entire quick-view phase (code 12),
  and the first long-view trial are absent** from the EEG. Present: long_view 19/20,
  words 20/20, final RS. First trigger at 51.6 s. Behavior/audio for the lost phases
  still exist; they're just not in the EEG.

### Things to review before trusting outputs
1. **ICA exclusions** are auto-detected from frontal channels (`Fp1/Fp2`, threshold
   2.5). Review `sub-01_ica_components.png` / the saved `_ica.fif` and set explicit
   excludes if needed.
2. **Bad channels:** QC (fig 05/07) flagged **T8** (~14× median) and **P7**
   (~4.5× median, drove the evoked) — failed dry electrodes. Both are listed in
   `preprocess.bad_channels` and interpolated before ICA. Re-check per subject.
3. **Artifact rejection is OFF by default** (`epoch.reject_uv: null`). Dry DSI-24
   channels run high (individual channels exceed 150 µV p2p every epoch). Add
   `autoreject` before group stats.
4. **Trigger mapping** (11=RS, 12=quick, 13=long, 14=words) — confirmed.
5. The pilot was recorded with `triggerhub-withSound`; the repo's `triggerhub-03`
   has its trigger code **disabled** (no markers in the generated script). Fix on the
   experiment side before collecting more subjects.
6. **Transcripts:** the STT pipeline (faster-whisper `small.en` + VAD, no-VAD
   fallback) transcribes most clips well. A few clips were spoken very quietly and
   stay empty/one-word — rows flagged `REVIEW` in `<sub>_transcripts.tsv`. For those,
   listen and correct by hand, or set `stt.model: medium.en` and re-run.
