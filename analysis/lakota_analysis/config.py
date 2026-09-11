"""Load ``analysis/config.yaml`` and resolve project paths.

Import this from anywhere:

    from lakota_analysis import CONFIG, paths, get_subject
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

# analysis/lakota_analysis/config.py  ->  analysis/  ->  repo root
ANALYSIS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ANALYSIS_DIR.parent
CONFIG_PATH = ANALYSIS_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
    CONFIG = yaml.safe_load(fh)


def _resolve(p: str | Path) -> Path:
    """Resolve a config path relative to the repo root (absolute passes through)."""
    p = Path(p)
    return p if p.is_absolute() else (REPO_ROOT / p)


paths = SimpleNamespace(
    repo_root=REPO_ROOT,
    analysis_dir=ANALYSIS_DIR,
    data_dir=_resolve(CONFIG["paths"]["data_dir"]),
    derivatives_dir=_resolve(CONFIG["paths"]["derivatives_dir"]),
)

subjects: list[str] = list(CONFIG["subjects"].keys())


def get_subject(sub: str) -> dict:
    """Return the config block for ``sub`` (raises KeyError if unknown)."""
    if sub not in CONFIG["subjects"]:
        raise KeyError(f"Unknown subject {sub!r}. Known: {subjects}")
    return CONFIG["subjects"][sub]


def source_dir(sub: str) -> Path:
    """Absolute path to a subject's raw source folder."""
    return paths.data_dir / get_subject(sub)["source_dir"]


def deriv_dir(sub: str, *parts: str) -> Path:
    """Absolute path under ``derivatives/<sub>/...`` (created on demand)."""
    d = paths.derivatives_dir / sub
    for p in parts:
        d = d / p
    d.mkdir(parents=True, exist_ok=True)
    return d


# convenient shortcuts
TRIGGERS: dict[str, int] = CONFIG["triggers"]
TRIGGERS_INV: dict[int, str] = {v: k for k, v in TRIGGERS.items()}
DESIGN = CONFIG["design"]
