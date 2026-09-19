"""Additive smoke tests — never touch prod files, only import + pure logic."""
import numpy as np


def test_whisper_fallback_absent_ok():
    from core import stt
    assert hasattr(stt, "transcribe_fallback")
    assert hasattr(stt, "is_offline_stt_available")
    assert isinstance(stt.is_offline_stt_available(), bool)


def test_whisper_fallback_returns_str():
    from core.stt import transcribe_fallback
    out = transcribe_fallback(np.zeros(1600, dtype=np.float32), model_name="tiny")
    assert isinstance(out, str)
