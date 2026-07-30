from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN = (
    ROOT
    / "docs/superpowers/specs/"
    "2026-07-31-advisor-governed-multimodal-evidence-composition-design.md"
)
PLAN = (
    ROOT
    / "docs/superpowers/plans/"
    "2026-07-31-advisor-governed-multimodal-evidence-composition-implementation.md"
)
ADR = (
    ROOT
    / "docs/decisions/0014-advisor-governed-multimodal-evidence-composition.md"
)


def _governance_text() -> str:
    return "\n".join(
        (
            DESIGN.read_text(encoding="utf-8"),
            PLAN.read_text(encoding="utf-8"),
            ADR.read_text(encoding="utf-8"),
        )
    )


def test_complementary_evidence_governance_closes_slice_zero_contract() -> None:
    governance = _governance_text()

    for required in (
        "1ca0a0b348638369e8407270ca5f363b0e551a9e",
        "d258c10dc40bd9eccd67c858b56f4e4cf5fe4610",
        "f828606741f636bca7ddbb66244ca60019eaa3c8",
        "cb1f4660ee4ac7d81b04ffea014362e933487e61",
        "not a runtime multi-agent system",
        "does **not** normalize a current DRA Markdown result",
        "disposable MKE store",
        "evaluation_canonical_source_id",
        "source_entry_canonical_id_v1",
        "eight public-safe synthetic cases",
        "four sealed holdouts",
        "Mechanism metrics",
        "Target metrics",
        "Guardrail metrics",
        "`capped`",
        "`inconclusive`",
        "`incremental_value_confirmed`",
        "`no_incremental_value`",
        "`evaluation_invalid`",
        "six ordered PRs",
        "Draft PR",
        "zero product tables/routes in Slice 0",
    ):
        assert required in governance


def test_slice_zero_documents_preserve_zero_product_mutation() -> None:
    governance = _governance_text()

    for prohibited in (
        "Slice 0 adds a product table",
        "Slice 0 adds a product route",
        "MKE and DRA call each other",
        "parse DRA Markdown into typed facts",
    ):
        assert prohibited not in governance
    assert "creates no product candidate" in governance
    assert "writes no Night Voyager business table" in governance


def test_complementary_evidence_plan_has_one_index_entry() -> None:
    index = (ROOT / "docs/superpowers/README.md").read_text(encoding="utf-8")
    scope = "Advisor-Governed Multimodal Evidence Composition"
    assert index.count(f"| {scope} |") == 1
    assert (
        "specs/2026-07-31-advisor-governed-multimodal-evidence-composition-design.md"
        in index
    )
    assert (
        "plans/2026-07-31-advisor-governed-multimodal-evidence-composition-"
        "implementation.md"
        in index
    )


def test_pre_reveal_freeze_has_distinct_roles_and_separate_commitments() -> None:
    governance = _governance_text()
    role_ids = (
        "independent-dataset-author-v2",
        "night-voyager-slice0-evaluator-v1",
        "independent-holdout-custodian-v2",
    )

    assert len(set(role_ids)) == 3
    for role_id in role_ids:
        assert role_id in governance
    for commitment in (
        "`payload_byte_length`",
        "`payload_sha256`",
        "`oracle_byte_length`",
        "`oracle_sha256`",
    ):
        assert commitment in governance
    assert "nv.slice0.one-way-reveal.v1" in governance


def test_revision_two_roles_reject_pre_admission_revision_one() -> None:
    governance = _governance_text()

    for required in (
        "`author_revision=2`",
        "`dataset_author_id=independent-dataset-author-v2`",
        "`evaluator_implementer_id=night-voyager-slice0-evaluator-v1`",
        "`holdout_custodian_id=independent-holdout-custodian-v2`",
        "`rejected_pre_admission`",
        "`deterministic_public_safe_synthetic_governed_fixture`",
    ):
        assert required in governance
    assert "dataset_author_id=independent-dataset-author-v1" not in governance
    assert "holdout_custodian_id=independent-holdout-custodian-v1" not in governance


def test_pre_reveal_ordering_freezes_complete_harness_before_observation() -> None:
    governance = " ".join(_governance_text().split())

    for required in (
        "before any eligible holdout producer observation",
        "A3 does not issue `PreRegistrationReceiptV2`",
        "A4 completes the reveal validator, tagged-wheel lane, frozen-suite harness, "
        "terminal verifier, and runner before final pre-registration",
        "A5 is one-shot reveal and execution only",
        "No code, test, evaluator, oracle, threshold, mapping, or eligible-source change "
        "is permitted after reveal",
        "preregistered three fresh-process determinism runs",
    ):
        assert required in governance


def test_governance_documents_have_no_trailing_whitespace() -> None:
    for path in (DESIGN, PLAN):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            assert line == line.rstrip(), f"{path.name}:{line_number}"
