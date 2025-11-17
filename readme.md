# Lakota Neuro Experiment – EEG + LSL Recording Guide

This document explains how to set up the DSI-24 headset, stream data over LabStreamingLayer (LSL), and record synchronized EEG + markers.

## Hardware / Software Requirements

- DSI-24 (or WearableSensing DSI headset)
- Windows laptop with DSI software
- PsychoPy experiment
- `dsi2lslGUI` (LSL EEG streamer)
- `run_lsl.py` (launches unified_receive.py)
- Python with `pylsl` installed

## Setup Instructions

### 1. Install dsi2lslGUI

Download from: https://github.com/labstreaminglayer/App-WearableSensing/releases

- Download latest Windows ZIP
- Extract to any folder
- Standalone `.exe` (not pip install)

### 2. Start DSI-Streamer

1. Launch DSI-Streamer
2. Select DSI-24 amplifier
3. Check impedances (< 50 kΩ recommended)
4. Press **PLAY**

⚠️ Keep DSI-Streamer running; `dsi2lslGUI` depends on it.

### 3. Start EEG LSL Stream

1. Launch `dsi2lslGUI.exe`
2. Set port to match DSI-Streamer's TCP/IP export setting
3. Set LSL stream name: `DSI-Stream`
4. Click **Start**

### 4. Run the Recorder

```bash
python run_lsl.py
```

Waits for both streams, launches `unified_receive.py`, saves to `session_recording.csv`.

### 5. Start PsychoPy Experiment

Your script creates an LSL marker stream: `PsychoPyMarkers`

## Typical Workflow

1. Start DSI-Streamer → PLAY
2. Start dsi2lslGUI → Start LSL
3. Run `run_lsl.py`
4. Run PsychoPy
5. Recorder starts automatically when streams appear


## Output Format

Data saved to `session_recording.csv` with columns: timestamp, ch1–ch24, marker

Markers = 0 during normal EEG; non-zero values indicate stimulus onset.

**Note:** Never record inside DSI-Streamer. All data recording happens via `run_lsl.py` → `unified_receive.py`.
