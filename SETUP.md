# Lakota Symbols Experiment — Setup Guide

How to run `lakota_symbols_triggerhub-02_lastrun.py` (**v2** — the version we use)
with the **DSI-24** EEG headset and the
**Trigger-Hub (MMBT)** marker box. Two configurations are described:

- **Setup A — Single computer** (one PC does both stimulation and EEG recording)
- **Setup B — Two computers** (one PC records EEG, the other runs stimulation)

The Trigger-Hub (MMBT) is plugged into the **stimulation** computer. It receives
trigger codes from PsychoPy over a serial (COM) port and sends them **wirelessly**
to a receiver dongle plugged into the DSI-24, which writes the marker directly into
the EEG — so the EEG and the stimulus onsets stay synchronized.

---

## 0. What you need

| Item | Notes |
|------|-------|
| DSI-24 headset | WearableSensing dry EEG |
| EEG Bluetooth dongle | Streams EEG from the headset; plugs into the **recording** computer |
| Trigger receiver dongle | Plugs into the **DSI-24**; receives trigger codes wirelessly from the MMBT |
| Trigger-Hub / **MMBT** box | Plugs into the **stimulation** computer via USB; shows up as **"Arduino Micro"** |
| MMBT USB drivers | Included in `mmbt/MMBT drivers/` |
| PsychoPy (Builder) | Run-time for the experiment |

---

## 1. Install PsychoPy (Builder)

Do this on whichever computer will run the stimulation (the **stim PC**).

1. Go to <https://www.psychopy.org/download.html>
2. Download the **Standalone PsychoPy** installer for Windows (use the 2025.1.x line
   to match the version the experiment was built with — `2025.1.1`).
3. Run the installer with default options. This installs **PsychoPy Builder**,
   **Coder**, and **Runner**.
4. Launch PsychoPy once to confirm it opens.

> The experiment uses `pyserial` to talk to the Trigger-Hub. It is bundled with
> Standalone PsychoPy, so no extra `pip install` is needed.

---

## 2. Install the Trigger-Hub (MMBT) driver — *stim PC only*

The MMBT enumerates as an **"Arduino Micro"** and needs its driver installed before
Windows assigns it a COM port.

1. Plug the MMBT into a USB port on the stim PC.
2. Install the driver from this repo: `mmbt/MMBT drivers/`
   - Easiest: run **`dpinst-amd64.exe`** (64-bit Windows) from that folder and
     follow the prompts. (Use `dpinst-x86.exe` on a 32-bit system.)
   - Or, in **Device Manager**, find the unrecognized **Arduino Micro**, choose
     **Update driver → Browse my computer**, and point it at the
     `mmbt/MMBT drivers/` folder.
3. Reference docs if needed: `mmbt/MMBT-S_Quickguide.pdf`,
   `mmbt/MMBT-S_instruction_manual_v2.1.pdf`.

### Find the COM port

1. Open **Device Manager → Ports (COM & LPT)**.
2. Locate **Arduino Micro (COMxx)** — note the number (e.g. `COM15`).

### Set the COM port in the experiment

Open `lakota_symbols_triggerhub-02_lastrun.py` and edit the serial line:

```python
ser = serial.Serial('COM15')
```

Change `COM15` to the COM number you found in Device Manager. Save the file.

> Tip: if the port number changes after re-plugging, you can pin it in Device
> Manager → the port's **Properties → Port Settings → Advanced → COM Port Number**.

---

## 3. Connect the markers (physical)

There are **two separate wireless links** — don't mix up their dongles:

```
TRIGGERS:  PsychoPy (stim PC) --USB--> MMBT (Arduino Micro) ))wireless)) trigger receiver dongle --plugged into--> DSI-24
EEG:       DSI-24 ))Bluetooth)) EEG dongle (recording PC) --> DSI-Streamer
```

- The **MMBT** is the trigger transmitter. PsychoPy writes a code to it over USB
  serial; the MMBT sends that code **wirelessly** to a small **receiver dongle that
  plugs into the DSI-24**, which injects the marker into the EEG.
- The **EEG Bluetooth dongle** is a *different* dongle that the DSI-24 streams EEG
  to; it plugs into the **recording PC** (see §4).

### Steps for the technician

1. **Stim PC:** plug the **MMBT** into USB. (Driver + COM port already done in §2 —
   it shows as **Arduino Micro**.)
2. **DSI-24:** plug the **trigger receiver dongle** into the DSI-24's trigger port.
3. Power on the MMBT / DSI-24
4. Plug the **EEG Bluetooth dongle** into the **recording PC** (this is the *other*
   dongle — used for streaming EEG in §4, not for triggers).
5. **Test before recording:** with DSI-Streamer running (§4), trigger a marker (run
   the task briefly, or use the MMBT test button) and confirm a non-zero value
   appears on the DSI trigger/event channel. If it stays at 0, the trigger link is
   not paired — re-check steps 2–3.

The experiment sets a trigger code at the start of each task phase and resets it
back to **0** at the end of that phase. See the [README](readme.md) for the full
code list.

---

## 4. Set up the DSI-24

On the **recording** computer:

1. Plug the **EEG Bluetooth dongle** into a USB port (this is the EEG-streaming
   dongle — **not** the trigger receiver dongle from §3, and **not** the PC's
   built-in Bluetooth).
2. Power on the DSI-24 headset and confirm it pairs with this dongle.
3. Launch **DSI-Streamer**.
4. Select the **DSI-24** amplifier / correct COM port for the dongle and
   **Connect**.
5. Fit the headset, check impedances (**< 50 kΩ** recommended).
6. Press **PLAY** to start streaming.

---

# Setup A — Single computer

One PC runs PsychoPy **and** records EEG. The MMBT and the EEG Bluetooth dongle are
both plugged into this one machine; the trigger receiver dongle is in the DSI-24.

**One-time setup**
1. Install PsychoPy Builder (§1).
2. Install the MMBT driver and set the COM port in the script (§2).

**Each session**
1. Plug in the **MMBT** (USB) and the **EEG Bluetooth dongle** (USB).
2. Plug the **trigger receiver dongle** into the DSI-24; confirm it pairs with the
   MMBT (§3).
3. Power on the DSI-24 and confirm it's paired with the EEG dongle.
4. Open **DSI-Streamer**, connect the DSI-24, check impedances, press **PLAY**.
   - (If recording via LSL: start `dsi2lslGUI` → Start, then `python run_lsl.py`.)
5. Open `lakota_symbols_triggerhub-02_lastrun.py` in **PsychoPy Coder** and confirm
   the COM port on line 417 matches the MMBT.
6. **Test trigger:** confirm a non-zero value appears on the DSI event channel (§3).
7. Click **Run** (green ▶). Enter participant / session in the dialog.
8. Run the task — the MMBT sends a code to the DSI at each phase as you go.
9. When finished, **stop** the recording in DSI-Streamer (or `run_lsl.py`).

---

# Setup B — Two computers

- **PC 1 — Recording PC:** EEG Bluetooth dongle + DSI-Streamer.
- **PC 2 — Stimulation PC:** MMBT (Trigger-Hub) + PsychoPy.
- The **trigger receiver dongle** lives in the DSI-24 (not in either PC).

Markers go **wirelessly** from PC 2's MMBT straight to the DSI-24, so the two
computers do **not** need to be networked for synchronization — the trigger code is
recorded directly inside the EEG by PC 1.

**One-time setup**
- PC 1: plug in the EEG dongle; install DSI-Streamer.
- PC 2: install PsychoPy Builder (§1); install the MMBT driver and set the COM
  port in the script (§2).

**Each session**

*On PC 2 (stimulation):*
1. Plug in the **MMBT** (USB); confirm it's the right COM port in line 417.
2. Plug the **trigger receiver dongle** into the DSI-24 and confirm it pairs with
   the MMBT (§3).

*On PC 1 (recording):*
3. Plug in the **EEG Bluetooth dongle**.
4. Power on the DSI-24, confirm pairing with the EEG dongle.
5. Open **DSI-Streamer**, connect DSI-24, check impedances, press **PLAY**.
6. (Optional LSL: `dsi2lslGUI` → Start, then `python run_lsl.py`.)
7. **Test trigger:** confirm a non-zero value appears on the DSI event channel (§3).

*On PC 2 (stimulation):*
8. Open `lakota_symbols_triggerhub-02_lastrun.py` in PsychoPy and click **Run** (▶).
9. Enter participant / session and run the task.

*After the run:*
8. Stop recording on PC 1. EEG (PC 1) and behavioral data (PC 2, in `data/`) are
   aligned through the shared trigger codes.

---

## Quick checklist

- [ ] PsychoPy Builder installed on the stim PC
- [ ] MMBT driver installed; **Arduino Micro** shows a COM port in Device Manager
- [ ] Running **v2** (`lakota_symbols_triggerhub-02_lastrun.py`)
- [ ] `ser = serial.Serial('COMxx')` (line ~417) matches that COM port
- [ ] **Trigger receiver dongle** plugged into the DSI-24, paired with the MMBT
- [ ] **EEG Bluetooth dongle** plugged into the recording PC
- [ ] DSI-24 powered on and paired (EEG dongle)
- [ ] Test trigger shows a non-zero value on the DSI event channel
- [ ] PsychoPy experiment **Run** → participant info entered
- [ ] DSI-Streamer connected, impedances OK, **RECORD** pressed

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `could not open port 'COM15'` | Wrong/occupied COM port. Close other apps using it, check Device Manager, update line 417. |
| MMBT not listed as Arduino Micro | Driver not installed — run `dpinst-amd64.exe` in `mmbt/MMBT drivers/`. |
| No triggers in EEG (event channel stays 0) | Trigger link not paired. Check MMBT is on USB (Arduino Micro), the **trigger receiver dongle** is seated in the DSI-24, and the two are paired (link LED). |
| DSI won't connect | Confirm the **EEG Bluetooth dongle** (not the PC's internal BT, not the trigger dongle) is used, headset is charged/on, correct COM port in DSI-Streamer. |
| COM number keeps changing | Pin it in Device Manager → Port Settings → Advanced → COM Port Number. |
