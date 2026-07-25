from pathlib import Path

from night_voyager.dra.live_storage import RECEIPT_NAMES


def test_recovery_receipts_cover_each_provider_free_stage_without_sessions() -> None:
    assert {
        "capture.json",
        "promotion.json",
        "review.json",
        "decision.json",
    }.issubset(RECEIPT_NAMES)
    source = Path(
        "src/night_voyager/dra/live_models.py"
    ).read_text(encoding="utf-8")
    receipt_source = source[source.index("class DraPromotionReceiptV1") :]
    for forbidden in (
        "session_value",
        "csrf_value",
        "cookie_value",
        "authorization_header",
    ):
        assert forbidden not in receipt_source


def test_cli_and_compose_expose_provider_free_full_rehearsal() -> None:
    cli = Path("scripts/verify_dra_live_closure.py").read_text(
        encoding="utf-8"
    )
    compose = Path("scripts/verify_compose.sh").read_text(encoding="utf-8")
    governed = Path("scripts/verify_dra_governed_flow.py").read_text(
        encoding="utf-8"
    )
    for command in ("promote", "review", "decide", "evaluate", "rehearse-full"):
        assert f'"{command}"' in cli
    assert "verify_dra_governed_flow.py --fixture" in compose
    assert "PostgresLiveOutcomeInspector" in governed
    assert "app.evidence_refs" not in governed
