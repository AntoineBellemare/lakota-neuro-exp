"""Make ``lakota_analysis`` importable regardless of the current directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> analysis/

# Windows consoles default to cp1252 and choke on ✅/⚠️ etc. — force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
