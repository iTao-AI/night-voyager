from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from types import FunctionType
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def verify_hygiene(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], None]:
    verifier = cast(
        FunctionType,
        runpy.run_path(str(ROOT / "scripts/verify_release.py"))["verify_public_hygiene"],
    )
    monkeypatch.setitem(verifier.__globals__, "ROOT", tmp_path)
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "web").mkdir()
    (tmp_path / "web/package-lock.json").write_text("{}", encoding="utf-8")
    return cast(Callable[[], None], verifier)


def test_public_hygiene_accepts_exact_root_ignore_rules(
    tmp_path: Path, verify_hygiene: Callable[[], None], capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".gitignore").write_text(
        "." + "sessions/\n." + "gstack/\n", encoding="utf-8"
    )

    verify_hygiene()

    assert "including both lockfiles" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("relative", "content"),
    (
        ("README.md", "." + "sessions/private.json"),
        ("README.md", "." + "gstack/state.json"),
        (".gitignore", "." + "sessions/private.json"),
        (".gitignore", "# ." + "sessions/ records"),
        ("docs/.gitignore", "." + "sessions/"),
        (".gitignore", "/" + "Users/private"),
        (".gitignore", "Developer/" + "Career"),
        (".gitignore", "BEGIN " + "PRIVATE KEY"),
        (".gitignore", "api_" + "key = 'private-value'"),
        ("uv.lock", "/" + "Users/private"),
        ("web/package-lock.json", "/" + "Users/private"),
    ),
)
def test_public_hygiene_still_rejects_private_content(
    tmp_path: Path, verify_hygiene: Callable[[], None], relative: str, content: str
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SystemExit, match="public-hygiene violations") as error:
        verify_hygiene()

    assert relative in str(error.value)
