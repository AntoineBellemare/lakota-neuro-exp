#!/usr/bin/env python3
"""
Wrapper launcher for WearableSensing unified_receive.py

✓ Waits for LSL streams BEFORE launching unified_receive.py
✓ Works with old pylsl versions where resolve_streams() has NO filters
✓ DSI-Stream     = optional (wait 10s max)
✓ PsychoPyMarkers = required (wait forever)
"""

import subprocess
import time
from pylsl import resolve_streams   # your version exposes THIS only

# ---------- CONFIG ----------
EEG_STREAM       = "DSI-Stream"
MARKER_STREAM    = "PsychoPyMarkers"
RECORD_TIME      = 600          # seconds
OUTPUT_FILE      = "session_recording.csv"
# ----------------------------


def stream_exists(name: str) -> bool:
    """Return True if any currently visible stream has that name."""
    try:
        streams = resolve_streams()   # NO args allowed in your pylsl
    except TypeError:
        streams = resolve_streams()   # Fallback – same thing
    for s in streams:
        if s.name() == name:
            return True
    return False


def wait_for_stream(name: str, required=True, timeout=None) -> bool:
    print(f"Waiting for stream: {name}")
    start = time.time()

    while True:
        if stream_exists(name):
            print(f"  ✓ Found {name}")
            return True

        if timeout is not None and (time.time() - start) > timeout:
            if required:
                raise RuntimeError(f"❌ Required stream '{name}' not found in {timeout}s.")
            else:
                print(f"  ⚠ Optional stream '{name}' NOT found after {timeout}s, continuing.")
                return False

        time.sleep(0.5)


# ---------------- RUN ---------------- #

available = []

# 1️⃣ EEG → optional
if wait_for_stream(EEG_STREAM, required=False, timeout=10.0):
    available.append(EEG_STREAM)

# 2️⃣ Markers → required
wait_for_stream(MARKER_STREAM, required=True, timeout=None)
available.append(MARKER_STREAM)

print("\n🚀 Streams detected → launching unified_receive.py\n")

cmd = [
    "python",
    "unified_receive.py",
    "--streams",
    *available,
    "--duration",
    str(RECORD_TIME),
    "--filename",
    OUTPUT_FILE,
]

print("Running:", " ".join(cmd))
print("Press CTRL+C to stop\n")
subprocess.run(cmd)
