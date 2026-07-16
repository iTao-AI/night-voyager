from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_published_v0_1_0_release_documents_are_immutable() -> None:
    expected = {
        "docs/releases/v0.1.0.md": (
            "a3251cdb572b4d982f989917f7e44d111cf887cf7fc8d75629cdd69c393d3a93"
        ),
        "docs/how-to/verify-v0.1.0-release.md": (
            "b65e18c6dc0e193e2de445ad41930230846bea3abfe43304f58f4cd133275ea3"
        ),
    }

    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
