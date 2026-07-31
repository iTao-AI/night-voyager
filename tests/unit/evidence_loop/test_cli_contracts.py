from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = (
    "evaluate_evidence_loop.py",
    "freeze_evidence_loop.py",
    "reveal_evidence_loop_holdouts.py",
    "verify_evidence_loop.py",
)


@pytest.mark.parametrize("script", SCRIPTS)
def test_a4_cli_help_is_public_and_successful(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("usage:")
    assert result.stderr == ""


@pytest.mark.parametrize("script", SCRIPTS)
def test_a4_cli_unknown_argument_is_one_bounded_diagnostic(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--not-approved"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert set(payload) == {"stage", "code", "problem", "cause", "recovery"}
    assert result.stderr.splitlines() == [f"recovery: {payload['recovery']}"]
    combined = result.stdout + result.stderr
    for forbidden in ("query", "cursor", "credential", str(ROOT), "custody-root"):
        assert forbidden not in combined


def test_development_cli_emits_canonical_receipt(tmp_path: Path) -> None:
    output = tmp_path / "development-evaluation-v2.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"),
            "--store-receipt",
            str(
                ROOT
                / "tmp/evidence-loop-a3-native-operator-final/receipts"
                / "sealed-mke-store-v1.json"
            ),
            "--output",
            str(output),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["code"] == "evidence_loop_development_evaluated"
    receipt = json.loads(output.read_bytes())
    assert receipt["terminal_disposition"] == "incremental_value_confirmed"
    assert result.stderr == ""


def test_reveal_rejects_invalid_freeze_before_custody_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = ROOT / "scripts/reveal_evidence_loop_holdouts.py"
    spec = importlib.util.spec_from_file_location("reveal_order_test", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    invalid_freeze = tmp_path / "pre-registration-v2.json"
    invalid_freeze.write_text("{}", encoding="utf-8")
    custody_observed = False

    def observe_custody(_root: Path) -> tuple[bytes, dict[str, Any]]:
        nonlocal custody_observed
        custody_observed = True
        return b"", {}

    def accept_mock_path(
        _repo_root: Path, _actual: Path, _relative: str
    ) -> None:
        return None

    monkeypatch.setattr(module, "_require_exact_path", accept_mock_path)
    monkeypatch.setattr(module, "_read_exact_custody_input", observe_custody)
    args = SimpleNamespace(
        pre_registration=invalid_freeze,
        holdout_manifest=ROOT
        / "tests/fixtures/evidence_loop/holdout-manifest-v1.json",
        store_root=ROOT
        / "tmp/evidence-loop-a3-native-operator-final/store",
        custody_root=tmp_path / "must-not-be-read",
        destination=ROOT
        / "tests/fixtures/evidence_loop/holdout-dataset-v1.json",
    )

    with pytest.raises(module.CliFailure) as raised:
        module._prepare(args)

    assert raised.value.exit_code == 13
    assert raised.value.payload["code"] == "pre_registration_invalid"
    assert custody_observed is False


@pytest.mark.parametrize(
    ("mutation", "exit_code", "code"),
    [
        (("selection", "status", "capped"), 12, "evaluation_inconclusive"),
        (("guardrails", "filesystem_mutation", True), 14, "mutation_prohibited"),
    ],
)
def test_development_cli_persists_each_terminal_disposition(
    tmp_path: Path,
    mutation: tuple[str, str, object],
    exit_code: int,
    code: str,
) -> None:
    dataset = json.loads(
        (ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json").read_text()
    )
    parent, key, value = mutation
    dataset["cases"][0][parent][key] = value
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    output = tmp_path / "must-not-exist.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(dataset_path),
            "--store-receipt",
            str(
                ROOT
                / "tmp/evidence-loop-a3-native-operator-final/receipts"
                / "sealed-mke-store-v1.json"
            ),
            "--output",
            str(output),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == exit_code
    assert json.loads(result.stdout)["code"] == code
    assert result.stderr.startswith("recovery: ")
    receipt = json.loads(output.read_bytes())
    assert receipt["terminal_disposition"] in {
        "inconclusive",
        "evaluation_invalid",
    }


@pytest.mark.parametrize(
    ("condition", "exit_code", "code"),
    [
        ("producer", 10, "store_receipt_invalid"),
        ("order", 11, "output_not_fresh"),
        ("validation", 13, "evaluation_invalid"),
    ],
)
def test_development_cli_completes_the_a4_failure_taxonomy(
    tmp_path: Path,
    condition: str,
    exit_code: int,
    code: str,
) -> None:
    dataset = ROOT / "tests/fixtures/evidence_loop/development-dataset-v1.json"
    store_receipt = (
        ROOT
        / "tmp/evidence-loop-a3-native-operator-final/receipts"
        / "sealed-mke-store-v1.json"
    )
    output = tmp_path / "evaluation.json"
    if condition == "producer":
        store_receipt = tmp_path / "store-receipt.json"
        store_receipt.write_text("{}", encoding="utf-8")
    elif condition == "order":
        output.write_text("occupied", encoding="utf-8")
    else:
        dataset = tmp_path / "dataset.json"
        dataset.write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/evaluate_evidence_loop.py"),
            "--development-dataset",
            str(dataset),
            "--store-receipt",
            str(store_receipt),
            "--output",
            str(output),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == exit_code
    assert json.loads(result.stdout)["code"] == code
    assert result.stderr.startswith("recovery: ")
