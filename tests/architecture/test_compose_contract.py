from pathlib import Path


def test_web_healthcheck_uses_ipv4_loopback() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert '"http://127.0.0.1:3000"' in compose


def test_compose_proof_executes_m3b_golden_flow_and_teardown() -> None:
    script = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    assert "verify_m3b_flow.py" in script
    assert "down --volumes --remove-orphans" in script
