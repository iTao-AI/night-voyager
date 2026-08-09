from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/assets/design/night-voyager-voyage-source.png"
SOURCE_SHA256 = "4fe73754e5180e725bfc7d734fc9a9039030da5ebef41f31aa1cf2f1ccff55fc"
SOURCE_BYTES = 1_662_495
SOURCE_SIZE = (1672, 941)
PRIVATE_OR_METADATA_MARKERS = (
    b"/" + b"Users/",
    b"." + b"gstack",
    b"Care" + b"er",
    b"Exif",
    b"EXIF",
    b"XMP ",
    b"http://ns.adobe.com/xap/",
)
LOCKED_DEPENDENCY_IDENTITIES = {
    "pyproject.toml": "bf5787b9aa88b5665fc99e29664f50ebac74996635390317f869bd74a1900805",
    "uv.lock": "42ed354a51331efb9c7566dcdce628f78baff1723a494741cf7fe78bdab9823f",
    "web/package.json": "4cfef58fd5ae42dede2984558ddd6541709b7021f34ddbbde50f22b027b163d0",
    "web/package-lock.json": (
        "00abdf8c8818dee085a428e21673969d6badcce3c6fbc46f974e2a1fa34697cc"
    ),
}
PRESENTATION_AUDIT = ROOT / "web/e2e/presentation.spec.ts"
M3A_MANIFEST = ROOT / "fixtures/m3a/manifest.json"
PLAN_EXECUTION_EVIDENCE = (
    ("docs/assets/plan-execution-current-action.png", 1440),
    ("docs/assets/plan-execution-advisor-review.png", 1440),
    ("docs/assets/plan-execution-reassessment-mobile.png", 390),
    ("docs/assets/plan-execution-recovery-mobile.png", 390),
)
APPROVED_PUBLIC_EVIDENCE_FILENAMES = (
    "night-voyager-portfolio-entry.png",
    "collaboration-confirmed-fact.png",
    "m5-advisor-ledger.png",
    "m5-family-receipt-timeline.png",
    "night-voyager-planning-revision.png",
    "plan-execution-current-action.png",
    "plan-execution-advisor-review.png",
    "plan-execution-reassessment-mobile.png",
    "plan-execution-recovery-mobile.png",
)
REMOVED_RUNTIME_ASSETS = tuple(
    "night-voyager-voyage-" + suffix
    for suffix in ("960.avif", "960.webp", "1680.avif", "1680.webp")
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def test_approved_source_identity_is_exact() -> None:
    assert SOURCE.is_file()
    data = SOURCE.read_bytes()
    assert len(data) == SOURCE_BYTES
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256
    assert _png_size(data) == SOURCE_SIZE
    assert all(marker not in data for marker in PRIVATE_OR_METADATA_MARKERS)


def test_runtime_voyage_assets_are_not_required_by_the_current_surface() -> None:
    runtime_directory = ROOT / "web/public/portfolio"
    for filename in REMOVED_RUNTIME_ASSETS:
        assert not (runtime_directory / filename).exists(), filename


def test_runtime_portfolio_directory_contains_no_png_source() -> None:
    runtime_directory = ROOT / "web/public/portfolio"
    assert not runtime_directory.exists() or not any(runtime_directory.glob("*.png"))


def test_dependency_manifests_and_locks_keep_the_approved_identity() -> None:
    for relative, expected_sha256 in LOCKED_DEPENDENCY_IDENTITIES.items():
        assert _sha256(ROOT / relative) == expected_sha256, relative


def test_root_presentation_is_responsive_reduced_motion_and_runtime_static() -> None:
    css = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("web/app/styles.css", "web/app/portfolio.css", "web/app/workspace.css")
    )
    component_paths = (
        ROOT / "web/components/presentation/PortfolioEntry.tsx",
        ROOT / "web/components/presentation/PortfolioShell.tsx",
        ROOT / "web/components/presentation/AdvisorWorkspacePreview.tsx",
        ROOT / "web/components/presentation/AdvisorWorkspaceShell.tsx",
        ROOT / "web/components/presentation/WorkflowRail.tsx",
    )
    assert all(path.is_file() for path in component_paths)
    components = "\n".join(path.read_text(encoding="utf-8") for path in component_paths)

    for token in (
        "--nv-frame",
        "--nv-canvas",
        ".advisor-portfolio-shell",
        ".advisor-workspace-shell",
        ".workflow-rail",
        "@media (max-width: 1023px)",
        "@media (max-width: 767px)",
        "@media (max-width: 389px)",
        "@media (prefers-reduced-motion: reduce)",
        "@media (min-width: 1280px)",
        "200%",
    ):
        assert token in css
    for forbidden in (
        "<canvas",
        "<video",
        "WebGL",
        "Math.random",
        "requestAnimationFrame",
        "onPointerMove",
        "pointermove",
        "night-voyager-voyage-" + "960",
        "night-voyager-voyage-" + "1680",
    ):
        assert forbidden not in components


def test_root_preview_projection_matches_the_closed_fixture_contract() -> None:
    manifest = json.loads(M3A_MANIFEST.read_text(encoding="utf-8"))
    projection = (ROOT / "web/lib/presentation/portfolio.ts").read_text(encoding="utf-8")
    case = manifest["case"]
    budget = case["family"]["budget"]

    assert f'intendedField: "{case["student"]["intended_field"]}"' in projection
    assert f'currency: "{budget["currency"]}"' in projection
    assert f'preferredMinor: {budget["preferred_minor"]:,}'.replace(",", "_") in projection
    assert f'hardCeilingMinor: {budget["hard_ceiling_minor"]:,}'.replace(",", "_") in projection

    expected_routes = []
    entries_by_country = {
        country: entry
        for country, entry in zip(
            case["student"]["preferred_countries"],
            manifest["source_pack"]["entries"],
            strict=True,
        )
    }
    for country in case["student"]["preferred_countries"]:
        entry = entries_by_country[country]
        expected_routes.append(
            (
                country,
                manifest["expected"][country],
                "complete" if not entry["known_gaps"] else "partial",
                entry["coverage"],
                entry["known_gaps"][0] if entry["known_gaps"] else None,
            )
        )

    route_pattern = re.compile(
        r'\{\n\s+id: "(?P<id>[^"]+)",\n'
        r'\s+outcome: "(?P<outcome>[^"]+)",\n'
        r'\s+evidenceSufficiency: "(?P<sufficiency>[^"]+)",\n'
        r'\s+acceptedEvidence: \[(?P<evidence>.*?)\],\n'
        r'\s+unresolvedGap: (?P<gap>null|"[^"]+"),\n\s+\}',
        re.DOTALL,
    )
    actual_routes = []
    for match in route_pattern.finditer(projection):
        actual_routes.append(
            (
                match["id"],
                match["outcome"],
                match["sufficiency"],
                re.findall(r'"([^"]+)"', match["evidence"]),
                None if match["gap"] == "null" else match["gap"].strip('"'),
            )
        )

    assert actual_routes == expected_routes
    assert 'proofSegment: "connected_same_case"' in projection
    assert 'nextAction: "review_routes"' in projection
    assert "Synthetic Australia Institution" not in projection
    assert "Synthetic Japan Institution" not in projection
    assert "Synthetic Malaysia Institution" not in projection


def test_governed_presentation_audit_harness_covers_the_approved_matrix() -> None:
    assert PRESENTATION_AUDIT.is_file()
    source = PRESENTATION_AUDIT.read_text(encoding="utf-8")

    for route in ('"/"', '"/demo/collaboration"', '"/demo"', '"/demo/plan"'):
        assert route in source
    for locale in ('"zh-CN"', '"en"'):
        assert locale in source
    for width in ("1440", "1024", "768", "390", "320"):
        assert width in source
    for required_contract in (
        "PRESENTATION_AUDIT_OUTPUT_DIR",
        "deviceScaleFactor",
        "200%",
        "keyboard",
        "focus",
        "reducedMotion",
        "contrast",
        "scrollWidth",
        "long-copy",
        "latest-64",
    ):
        assert required_contract in source


def test_governed_presentation_audit_harness_enforces_semantic_authority() -> None:
    source = PRESENTATION_AUDIT.read_text(encoding="utf-8")

    for required_enforcement in (
        "requiredRatio",
        "sample.ratio < sample.requiredRatio",
        "entry.clipped",
        "maxMotionMs",
        "activateByKeyboard",
        "keyboard journey",
        'locator("summary")',
    ):
        assert required_enforcement in source


@pytest.mark.parametrize(("relative", "expected_width"), PLAN_EXECUTION_EVIDENCE)
def test_plan_execution_evidence_is_sanitized_png(
    relative: str,
    expected_width: int,
) -> None:
    path = ROOT / relative
    assert path.is_file(), relative
    data = path.read_bytes()
    width, height = _png_size(data)
    assert width == expected_width
    assert expected_width <= height < 10_000
    assert 10_000 < len(data) < 2_000_000
    assert all(marker not in data for marker in PRIVATE_OR_METADATA_MARKERS)


def test_plan_execution_evidence_is_generated_from_semantic_state_assertions() -> None:
    source = PRESENTATION_AUDIT.read_text(encoding="utf-8")
    for filename in (
        "plan-execution-current-action.png",
        "plan-execution-advisor-review.png",
        "plan-execution-reassessment-mobile.png",
        "plan-execution-recovery-mobile.png",
    ):
        assert filename in source
    assert "PRESENTATION_PUBLIC_EVIDENCE_ROOT" in source
    assert '"Local synthetic demo"' in source
    assert '"本地合成演示"' in source


def test_browser_presentation_contract_is_advisor_first_and_keeps_the_execution_boundary_visible() -> None:
    bootstrap = (ROOT / "web/e2e/bootstrap.spec.ts").read_text(encoding="utf-8")
    design_review = (ROOT / "web/e2e/portfolio-design-review.spec.ts").read_text(
        encoding="utf-8"
    )
    source = PRESENTATION_AUDIT.read_text(encoding="utf-8")

    assert "AI collaboration workspace for study-abroad advisors" in bootstrap
    assert "留学顾问的 AI 协作工作台" in bootstrap
    assert "APPROVED_PUBLIC_EVIDENCE_FILENAMES" in source
    for filename in APPROVED_PUBLIC_EVIDENCE_FILENAMES:
        assert filename in source
    assert "data-proof-segment" in source
    assert "data-primary-action" in source
    assert "connected_same_case" in source
    assert "independent_execution_scenario" in source
    assert "portfolio-category" in design_review
    assert "Family input" not in bootstrap
    assert "Family decision" not in bootstrap
