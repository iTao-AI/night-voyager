from pathlib import Path


def test_postgres_inspector_uses_only_migration_0011_strict_projection() -> None:
    source = (
        Path(__file__).resolve().parents[3]
        / "src/night_voyager/dra/live_outcome_postgres.py"
    ).read_text(encoding="utf-8")
    assert "app.project_dra_live_outcome" in source
    assert "DraLiveOutcomeProjectionV2" in source
    assert "producer_repository" in source
    assert "request_identity_sha256" in source
    assert "dra_research_candidates" not in source
    assert "external_evidence_verifications" not in source
    assert "INSERT " not in source
    assert "UPDATE " not in source
    assert "DELETE " not in source
