from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def tracked_and_pending_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return [ROOT / item.decode() for item in output.split(b"\0") if item]


def verify_public_hygiene() -> None:
    forbidden = (
        "/" + "Users/",
        "." + "sessions/",
        "." + "gstack/",
        "Developer/" + "Career",
        "BEGIN " + "PRIVATE KEY",
    )
    credential = re.compile(r"(?i)(api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]+['\"]")
    violations: list[str] = []
    for path in tracked_and_pending_files():
        if not path.is_file() or path.suffix in {".lock", ".png", ".jpg", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(value in text for value in forbidden) or credential.search(text):
            violations.append(str(path.relative_to(ROOT)))
    if violations:
        raise SystemExit(f"public-hygiene violations: {', '.join(violations)}")
    print("public-hygiene: tracked and pending text files passed")


def verify_wheel() -> None:
    run("uv", "build", "--wheel")
    wheel = max((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
    with tempfile.TemporaryDirectory(prefix="night-voyager-wheel-") as temp:
        environment = os.environ.copy()
        environment["UV_PROJECT_ENVIRONMENT"] = str(Path(temp) / ".venv")
        run("uv", "venv", environment["UV_PROJECT_ENVIRONMENT"], "--python", "3.12.13")
        python = f"{environment['UV_PROJECT_ENVIRONMENT']}/bin/python"
        run("uv", "pip", "install", "--python", python, str(wheel))
        run(
            f"{environment['UV_PROJECT_ENVIRONMENT']}/bin/python",
            "-c",
            "from night_voyager.api import create_app; "
            "assert create_app().title == 'Night Voyager API'",
        )
    print(f"wheel-smoke: isolated import and app factory passed ({wheel.name})")


def main() -> None:
    verify_public_hygiene()
    verify_wheel()


if __name__ == "__main__":
    main()
