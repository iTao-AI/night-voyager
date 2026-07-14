from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_verifier():
    path = ROOT / "scripts/verify_release.py"
    spec = importlib.util.spec_from_file_location("verify_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_verifier_checks_the_public_v0_1_0_surface(
    capsys: pytest.CaptureFixture[str],
) -> None:
    verifier = load_verifier()

    verifier.verify_release_surface()

    output = capsys.readouterr().out
    assert "proof release surface: v0.1.0 local synthetic portfolio contract confirmed" in output
