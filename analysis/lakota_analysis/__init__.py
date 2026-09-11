"""Lakota Neuro — analysis package.

Small, config-driven toolkit for the Lakota-symbols EEG + audio experiment:

    io            locate and load a subject's EEG / behavioral / audio data
    qc            sanity checks (triggers, behavioral responses, audio)
    eeg_preprocess   filter / re-reference / ICA cleaning
    eeg_epochs    build condition epochs from the trigger channel
    stt           transcribe spoken word-associations (faster-whisper)

Everything is parameterised in ``analysis/config.yaml``.
"""
from .config import CONFIG, paths, subjects, get_subject

__all__ = ["CONFIG", "paths", "subjects", "get_subject"]
