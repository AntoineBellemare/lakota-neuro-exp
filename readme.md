# Lakota Symbols — EEG Experiment (DSI-24 + Trigger-Hub)

PsychoPy experiment that presents a series of Lakota visual symbols while EEG is
recorded with a WearableSensing **DSI-24** headset. Stimulus events are marked
directly in the EEG via a **Trigger-Hub (MMBT)** marker box.

## Quick start

See **[SETUP.md](SETUP.md)** for the full hardware + software setup — driver
install, COM-port configuration, trigger wiring, and both the **single-computer**
and **two-computer** configurations.

## What's in this repo

| Path | What it is |
|------|------------|
| `lakota_symbols_triggerhub-02.psyexp` | The experiment — open in PsychoPy Builder |
| `lakota_symbols_triggerhub-02_lastrun.py` | Generated script — the file you actually run; set the MMBT COM port here |
| `stimuli/` + `stimuli_list.xlsx` | Symbol images and the trial list |
| `mmbt/` | MMBT (Trigger-Hub) USB drivers + quickguide |
| `SETUP.md` | Setup & operation guide |

## Experiment flow

1. **Resting state** — fixation cross.
2. **Quick viewing** — each symbol shown briefly (~1 s), repeated 2×.
3. **Longer viewing** — each symbol shown once (~5 s), then a *meaningfulness* rating.
4. **Words** — each symbol shown once more; the participant writes 10 associated words.
5. **Resting state** — fixation cross.

There are 20 symbols, shown in random order within each phase.

## Trigger codes

The experiment writes a single byte to the MMBT at the start of each phase and
resets it to `0` at the end (a **tonic** marker — it stays at the code value for the
whole phase, then drops to 0 between phases).

| Code | Phase |
|------|-------|
| `11` | Resting state (start and end) |
| `12` | Quick viewing (image onset) |
| `13` | Longer viewing (long onset) + meaningfulness rating |
| `14` | Words (word-association) |
| `0`  | Baseline (between phases) |

## Data

EEG is recorded in **DSI-Streamer** on the recording PC. PsychoPy behavioral data
(ratings, words, timestamps) is written under `data/`. Recordings and pilot data are
kept local (git-ignored).

## Old LSL setup (archived)

The previous LabStreamingLayer recording approach — the `dsi2lsl` streamer plus
`run_lsl.py` / `unified_receive.py` and the standalone `lakota_symbols_lsl`
experiment — lives on the **[`lsl-setup`](../../tree/lsl-setup)** branch, together
with its own README. `main` uses the hardware Trigger-Hub path described above.
