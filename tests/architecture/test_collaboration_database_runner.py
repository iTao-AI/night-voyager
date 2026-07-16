from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_make_exposes_the_bounded_collaboration_database_runner() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "collaboration-db-check:" in makefile
    assert 'SUITE="$(SUITE)" scripts/run_collaboration_db_tests.sh' in makefile


def test_collaboration_database_runner_is_disposable_and_suite_bounded() -> None:
    source = (ROOT / "scripts/run_collaboration_db_tests.sh").read_text(
        encoding="utf-8"
    )
    for suite in ("repository", "http", "authority"):
        assert suite in source
    assert source.index("unknown collaboration database suite") < source.index(
        "docker compose"
    )
    assert "PYTEST_ADDOPTS=" in source
    assert "-m database" in source
    assert "down --volumes --remove-orphans" in source
