from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.2"
FASTAPI_VERSION_FLOOR = (0, 139, 2)
FASTAPI_VERSION_CEILING = (0, 140)
RELEASE_TAG = f"v{VERSION}"
RELEASE_ARCHIVE_URL = (
    f"https://github.com/iTao-AI/night-voyager/archive/refs/tags/{RELEASE_TAG}.tar.gz"
)
RELEASE_ARCHIVE_ROOT = f"night-voyager-{VERSION}"
DESCRIPTION = "Evidence-grounded advisor-to-family decision workflow with durable Agent tasks"
POSTGRES_IMAGE = (
    "postgres:18.4-alpine3.24@sha256:"
    "9a8afca54e7861fd90fab5fdf4c42477a6b1cb7d293595148e674e0a3181de15"
)
M3A_TABLES = {
    "student_cases",
    "student_case_revisions",
    "source_packs",
    "source_pack_entries",
    "evidence_refs",
    "planning_runs",
    "planning_routes",
    "comparison_dimensions",
    "comparison_dimension_evidence_refs",
    "cost_evidence",
    "ranking_evidence",
}
M3B_TABLES = {
    "student_case_participants",
    "advisor_reviews",
    "evidence_risk_acceptances",
    "decision_briefs",
    "family_decisions",
    "timeline_plans",
    "audit_events",
    "idempotency_records",
}
M4A_TABLES = {"agent_tasks", "agent_executions", "agent_task_events"}
DRA_TABLES = {"dra_research_candidates", "external_evidence_verifications"}
COLLABORATION_TABLES = {
    "collaboration_threads",
    "message_events",
    "memory_candidates",
    "memory_candidate_verifications",
    "confirmed_facts",
    "case_revision_confirmed_fact_refs",
}
COLLABORATION_API_FUNCTIONS = {
    "create_collaboration_thread",
    "append_collaboration_message",
    "propose_memory_candidate",
    "verify_memory_candidate",
    "read_collaboration_thread",
    "read_collaboration_messages",
    "read_memory_candidates",
    "read_confirmed_facts",
}
SKILL_TABLES = {
    "skill_definitions",
    "skill_versions",
    "skill_change_candidates",
    "skill_evaluation_results",
    "skill_activation_events",
}
SKILL_API_FUNCTIONS = {
    "create_skill_change_candidate",
    "record_skill_candidate_evaluation",
    "promote_skill_change_candidate",
    "rollback_skill_activation",
    "list_skill_catalog",
    "get_skill_catalog_item",
    "load_skill_candidate_context",
    "inspect_planning_skill",
}
SKILL_WORKER_FUNCTIONS = {
    "load_agent_task_skill_pin",
    "load_persisted_synthetic_planning_snapshot",
}
IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "dist",
    "node_modules",
}
BINARY_SUFFIXES = {".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".webp"}
M5_SCREENSHOTS = (
    "docs/assets/m5-advisor-ledger.png",
    "docs/assets/m5-family-receipt-timeline.png",
)
RELEASE_DOCUMENTS = (
    f"docs/releases/v{VERSION}.md",
    f"docs/how-to/verify-v{VERSION}-release.md",
)
PUBLISHED_RELEASE_DOCUMENTS = {
    "docs/releases/v0.1.0.md": "a3251cdb572b4d982f989917f7e44d111cf887cf7fc8d75629cdd69c393d3a93",
    "docs/how-to/verify-v0.1.0-release.md": (
        "b65e18c6dc0e193e2de445ad41930230846bea3abfe43304f58f4cd133275ea3"
    ),
    "docs/releases/v0.1.1.md": "0e7724ca54a9d9c8b3ed403f6bbbd86c04dde3ee79e0644e95ee3ccf90513ab2",
    "docs/how-to/verify-v0.1.1-release.md": (
        "3e20b41e3256c275d557e6165e7e224a95a3a642286f6993da209a51aebe8f16"
    ),
}
RELEASE_HEADINGS = (
    "## Summary",
    "## Completion",
    "## Verification",
    "## Scope",
    "## Risk / Impact",
    "## Documentation impact",
)
RELEASE_NOTE_TOKENS = (
    "local synthetic portfolio release",
    "Governed Collaboration Core v1",
    "MessageEvent",
    "MemoryCandidate",
    "advisor verification",
    "ConfirmedFact",
    "Case revision",
    "versioned Skill",
    "activation",
    "rollback",
    "runtime task",
    "/demo/collaboration",
    "read-only Planning Skill inspector",
    "task-free",
    "GitHub-generated source archive",
    "Live provider proof was not run",
)
RELEASE_HOW_TO_TOKENS = (
    "git fetch origin --tags --prune",
    "git status --short --branch",
    "git rev-parse HEAD",
    "git rev-parse origin/main",
    "git describe --tags --exact-match HEAD",
    f"git cat-file -t {RELEASE_TAG}",
    f"git rev-parse {RELEASE_TAG}^{{tag}}",
    f"git rev-parse {RELEASE_TAG}^{{commit}}",
    'curl --fail --location --output "$archive"',
    RELEASE_ARCHIVE_URL,
    'wc -c "$archive"',
    'shasum -a 256 "$archive"',
    'tar -xzf "$archive" -C "$tmp_dir"',
    f'cd "$tmp_dir/{RELEASE_ARCHIVE_ROOT}"',
    "make doctor",
    "make collaboration-check",
    "make skills-check",
    "make dra-check",
    "make db-check",
    "make check",
    "make proof",
    "make compose-proof",
    "make down",
    "docker compose ps --all",
    "object type `tag`",
    "Never move the tag after publication",
    "Use the extracted source archive",
    "normal pull request",
    f"Do not force-move `{RELEASE_TAG}`",
    "bypass the `main` ruleset",
)
DRA_SURFACE = (
    "scripts/verify_dra_consumer.py",
    "scripts/verify_dra_governed_flow.py",
    "scripts/run_dra_lane.sh",
    "scripts/seed_dra_proof.py",
    "docs/decisions/0007-dra-governed-mixed-evidence-boundary.md",
    "docs/reference/dra-governed-evidence.md",
    "docs/operations/dra-consumer-proof.md",
)
COLLABORATION_SURFACE = (
    "migrations/versions/0007_conversation_and_memory.py",
    "src/night_voyager/interfaces/http/collaboration.py",
    "scripts/run_collaboration_db_tests.sh",
    "scripts/verify_collaboration_flow.py",
    "docs/decisions/0008-governed-collaboration-and-memory-authority.md",
    "docs/reference/collaboration-and-confirmed-facts.md",
    "docs/operations/collaboration-authority.md",
)
PR_C_BFF_ROUTE_METHODS = {
    "web/app/api/demo/cases/[caseId]/collaboration-thread/route.ts": ("GET",),
    "web/app/api/demo/collaboration-threads/[threadId]/messages/route.ts": ("GET", "POST"),
    "web/app/api/demo/messages/[messageId]/memory-candidates/route.ts": ("POST",),
    "web/app/api/demo/cases/[caseId]/memory-candidates/route.ts": ("GET",),
    "web/app/api/demo/memory-candidates/[candidateId]/verification-decisions/route.ts": ("POST",),
    "web/app/api/demo/cases/[caseId]/confirmed-facts/route.ts": ("GET",),
    "web/app/api/demo/cases/[caseId]/planning-skill-inspector/route.ts": ("GET",),
}
PR_C_BROWSER_SURFACE = (
    "web/app/demo/collaboration/page.tsx",
    *PR_C_BFF_ROUTE_METHODS,
    "web/components/collaboration-demo/CollaborationDemo.tsx",
    "web/components/collaboration-demo/CollaborationRecoveryNotice.tsx",
    "web/components/collaboration-demo/ConfirmedFactSummary.tsx",
    "web/components/collaboration-demo/MemoryCandidateCard.tsx",
    "web/components/collaboration-demo/SharedThread.tsx",
    "web/components/skill-inspector/PlanningSkillInspector.tsx",
    "web/lib/collaboration-demo/api.ts",
    "web/lib/collaboration-demo/contracts.ts",
    "web/lib/collaboration-demo/reducer.ts",
    "web/lib/collaboration-demo/use-collaboration-demo.ts",
    "web/lib/skill-inspector/contracts.ts",
    "web/lib/connected-demo/session-storage.ts",
    "web/lib/connected-demo/use-connected-demo.ts",
    "web/e2e/collaboration-demo.spec.ts",
    "web/playwright.compose.config.ts",
    "scripts/verify_compose.sh",
    "docs/operations/collaboration-walkthrough.md",
    "docs/assets/collaboration-confirmed-fact.png",
    "README.md",
    "README_CN.md",
)
SKILL_SURFACE = (
    "migrations/versions/0008_versioned_skills.py",
    "fixtures/skills/runtime-manifest-v1.json",
    "fixtures/skills/eval-manifest-v1.json",
    "src/night_voyager/skills/registry.py",
    "src/night_voyager/skills/evaluation.py",
    "docs/decisions/0009-versioned-skill-runtime-pinning.md",
    "docs/reference/versioned-skills-and-runtime-pins.md",
    "docs/operations/skill-governance.md",
)

os.environ.setdefault("UV_BUILD_CONSTRAINT", "build-constraints.txt")
os.environ.setdefault("UV_REQUIRE_HASHES", "1")


def run(*command: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def git_available() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def source_files() -> list[Path]:
    if git_available():
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        return [ROOT / item.decode() for item in output.split(b"\0") if item]

    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.parts)
    ]


def verify_tree_mode(mode: str) -> None:
    if mode == "snapshot":
        if git_available():
            raise SystemExit("snapshot proof must run from a Git-free Docker build context")
        print("proof tree: Docker snapshot context confirmed")
        return

    if not git_available():
        raise SystemExit(f"{mode} proof requires a Git checkout")
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if mode == "release" and status:
        raise SystemExit("release proof requires a clean Git tree")
    state = "clean" if not status else "development tree with pending changes"
    print(f"proof tree: {state} ({mode} mode)")


def verify_public_hygiene() -> None:
    forbidden = (
        "/" + "Users/",
        "." + "sessions/",
        "." + "gstack/",
        "Developer/" + "Career",
        "BEGIN " + "PRIVATE KEY",
    )
    credential = re.compile(r"(?i)(api[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]+['\"]")
    scanned: list[str] = []
    violations: list[str] = []
    for path in source_files():
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        relative = str(path.relative_to(ROOT))
        scanned.append(relative)
        if any(value in text for value in forbidden) or credential.search(text):
            violations.append(relative)
    if violations:
        raise SystemExit(f"public-hygiene violations: {', '.join(violations)}")
    if "uv.lock" not in scanned or "web/package-lock.json" not in scanned:
        raise SystemExit("public-hygiene must scan both lockfiles")
    print(f"proof hygiene: {len(scanned)} readable source files scanned, including both lockfiles")


def verify_m5_public_evidence() -> None:
    public_entries = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "README_CN.md")
    }
    for relative in M5_SCREENSHOTS:
        if not (ROOT / relative).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise SystemExit(f"missing or invalid M5 screenshot: {relative}")
        if any(source.count(relative) != 1 for source in public_entries.values()):
            raise SystemExit(f"each README must reference the M5 screenshot once: {relative}")
    print("proof M5 evidence: connected runbook and two PNG screenshots present")


def verify_dra_surface() -> None:
    if any(not (ROOT / relative).is_file() for relative in DRA_SURFACE):
        raise SystemExit("governed DRA proof surface incomplete")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    reference = (ROOT / "docs/reference/dra-governed-evidence.md").read_text(
        encoding="utf-8"
    )
    operations = (ROOT / "docs/operations/dra-consumer-proof.md").read_text(
        encoding="utf-8"
    )
    if (
        "dra-check:" not in makefile
        or "dra-consumer-proof:" not in makefile
        or "make dra-check" not in workflow
        or "dra-consumer-proof" in workflow
        or "generate_governed_mixed_planning_run_v1" not in reference
        or "australia_program_fit -> program_fit -> externally_verified"
        not in reference
        or "exact copies of the synthetic baseline" not in reference
        or "Live provider proof was not run" not in operations
        or "make compose-proof" not in operations
    ):
        raise SystemExit("governed DRA command or status contract drift")
    print("proof DRA surface: offline governed mixed decision closure confirmed")


def verify_collaboration_surface() -> None:
    if any(not (ROOT / relative).is_file() for relative in COLLABORATION_SURFACE):
        raise SystemExit("governed collaboration proof surface incomplete")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    compose_proof = (ROOT / "scripts/verify_compose.sh").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    adr = (ROOT / COLLABORATION_SURFACE[4]).read_text(encoding="utf-8")
    reference = (ROOT / COLLABORATION_SURFACE[5]).read_text(encoding="utf-8")
    operations = (ROOT / COLLABORATION_SURFACE[6]).read_text(encoding="utf-8")
    walkthrough_path = ROOT / "docs/operations/collaboration-walkthrough.md"
    walkthrough = walkthrough_path.read_text(encoding="utf-8") if walkthrough_path.is_file() else ""
    migration = (ROOT / COLLABORATION_SURFACE[0]).read_text(encoding="utf-8")
    if (
        "collaboration-check:" not in makefile
        or "make collaboration-check" not in workflow
        or "python scripts/verify_collaboration_flow.py" not in compose_proof
        or "verify_collaboration_flow.py --verify-existing" not in compose_proof
        or "collaboration-and-confirmed-facts.md" not in docs_index
        or "collaboration-authority.md" not in docs_index
        or "0008-governed-collaboration-and-memory-authority.md" not in docs_index
        or "- Status: Accepted" not in adr
        or "adds exactly these six" not in adr
        or "FastAPI exposes exactly eight" not in adr
        or "app.case_revision_confirmed_fact_refs" not in reference
        or "PR B Skill governance" not in reference
        or "Case FOR UPDATE -> superseded PlanningRun update" not in reference
        or "make collaboration-db-check SUITE=authority" not in operations
        or "PR C browser walkthrough" not in operations
        or "/demo/collaboration" not in walkthrough
        or "does not create" not in walkthrough
        or "server-owned" not in walkthrough
        or 'revision = "0007"' not in migration
        or 'down_revision = "0006"' not in migration
        or "CREATE OR REPLACE FUNCTION app.persist_planning_result(" not in migration
        or "LEGACY_PLANNING_PERSISTENCE_SQL" not in migration
    ):
        raise SystemExit("governed collaboration command, status, or documentation drift")
    verify_pr_c_browser_surface()
    print("proof collaboration surface: governed conversation and memory authority confirmed")


def verify_pr_c_browser_surface() -> None:
    if any(not (ROOT / relative).is_file() for relative in PR_C_BROWSER_SURFACE):
        raise SystemExit("PR C browser proof surface incomplete")

    method_count = 0
    for relative, expected in PR_C_BFF_ROUTE_METHODS.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        actual = tuple(re.findall(r"export async function (GET|POST)\b", source))
        if actual != expected:
            raise SystemExit(f"PR C BFF route method drift: {relative}")
        method_count += len(actual)
    if len(PR_C_BFF_ROUTE_METHODS) != 7 or method_count != 8:
        raise SystemExit("PR C BFF route inventory drift")

    page = (ROOT / "web/app/demo/collaboration/page.tsx").read_text(encoding="utf-8")
    walkthrough = (
        ROOT / "web/components/collaboration-demo/CollaborationDemo.tsx"
    ).read_text(encoding="utf-8")
    hook = (ROOT / "web/lib/collaboration-demo/use-collaboration-demo.ts").read_text(
        encoding="utf-8"
    )
    inspector = (
        ROOT / "web/components/skill-inspector/PlanningSkillInspector.tsx"
    ).read_text(encoding="utf-8")
    playwright = (ROOT / "web/playwright.compose.config.ts").read_text(encoding="utf-8")
    browser_spec = (ROOT / "web/e2e/collaboration-demo.spec.ts").read_text(encoding="utf-8")
    compose_proof = (ROOT / "scripts/verify_compose.sh").read_text(encoding="utf-8")
    required_tokens = (
        "CollaborationDemo" in page,
        "useCollaborationDemo" in walkthrough,
        "PlanningSkillInspector" in walkthrough,
        "confirmation_submitting" in hook,
        "confirmedFacts" in hook,
        "server-owned planning execution record" in inspector,
        '"collaboration-demo.spec.ts"' in playwright,
        'page.goto("/demo/collaboration")' in browser_spec,
        "{ width: 1440" in browser_spec,
        "{ width: 768" in browser_spec,
        "{ width: 390" in browser_spec,
        "collaboration-confirmed-fact.png" in browser_spec,
        "UPDATE_COLLABORATION_SCREENSHOT" in compose_proof,
        "new EventSource" not in hook,
    )
    if not all(required_tokens):
        raise SystemExit("PR C browser proof surface drift")

    screenshot = (ROOT / "docs/assets/collaboration-confirmed-fact.png").read_bytes()
    if not screenshot.startswith(b"\x89PNG\r\n\x1a\n") or len(screenshot) < 24:
        raise SystemExit("PR C browser screenshot invalid")
    width = int.from_bytes(screenshot[16:20], "big")
    height = int.from_bytes(screenshot[20:24], "big")
    if width != 1440 or height < 900:
        raise SystemExit("PR C browser screenshot dimensions drift")

    for relative in ("README.md", "README_CN.md"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        if (
            source.count("/demo/collaboration") < 1
            or source.count("docs/operations/collaboration-walkthrough.md") < 1
            or source.count("docs/assets/collaboration-confirmed-fact.png") != 1
        ):
            raise SystemExit(f"PR C README discovery drift: {relative}")
    print(
        "proof PR C browser surface: seven explicit routes, eight methods, "
        "Chromium walkthrough, screenshot, and read-only inspector confirmed"
    )


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_skill_surface() -> None:
    if any(not (ROOT / relative).is_file() for relative in SKILL_SURFACE):
        raise SystemExit("versioned Skill governance surface incomplete")

    from night_voyager.identity.demo_seed import build_demo_skill_seed
    from night_voyager.skills.evaluation import SkillEvaluator
    from night_voyager.skills.registry import SkillRuntimeRegistry

    runtime_manifest = json.loads((ROOT / SKILL_SURFACE[1]).read_text(encoding="utf-8"))
    evaluation_manifest = json.loads((ROOT / SKILL_SURFACE[2]).read_text(encoding="utf-8"))
    runtime_content = {
        key: value for key, value in runtime_manifest.items() if key != "manifest_sha256"
    }
    evaluation_content = {
        key: value for key, value in evaluation_manifest.items() if key != "manifest_sha256"
    }
    runtime_identities = tuple(
        (entry["skill_key"], entry["version"], entry["binding_kind"])
        for entry in runtime_manifest.get("entries", ())
    )
    expected_runtime_identities = (
        ("student-profile-intake", "1.0.0", "catalog_only"),
        ("study-destination-compare", "1.0.0", "planning_runtime"),
        ("study-destination-compare", "1.0.1", "planning_runtime"),
        ("evidence-research", "1.0.0", "catalog_only"),
        ("document-evidence-retrieval", "1.0.0", "catalog_only"),
        ("family-decision-brief", "1.0.0", "catalog_only"),
        ("application-timeline-guard", "1.0.0", "catalog_only"),
    )
    evaluation_identities = tuple(
        (dataset["skill_key"], dataset["version"])
        for dataset in evaluation_manifest.get("datasets", ())
    )
    packaged_registry = SkillRuntimeRegistry.from_json(
        (ROOT / SKILL_SURFACE[1]).read_bytes()
    )
    packaged_evaluator = SkillEvaluator.from_json(
        (ROOT / SKILL_SURFACE[2]).read_bytes(), packaged_registry
    )
    seed = build_demo_skill_seed(packaged_registry, packaged_evaluator)
    seed_entries = seed.get("entries")
    seed_identities_list: list[tuple[str, str]] = []
    seed_activation_count = 0
    if isinstance(seed_entries, list):
        for raw_entry in cast(list[object], seed_entries):
            if not isinstance(raw_entry, dict):
                break
            entry = cast(dict[str, object], raw_entry)
            raw_manifest = entry.get("manifest")
            if not isinstance(raw_manifest, dict):
                break
            manifest = cast(dict[str, object], raw_manifest)
            skill_key = manifest.get("skill_key")
            version = manifest.get("version")
            if not isinstance(skill_key, str) or not isinstance(version, str):
                break
            seed_identities_list.append((skill_key, version))
            seed_activation_count += int("activation_event_id" in entry)
    seed_identities = tuple(seed_identities_list)
    if (
        runtime_manifest.get("manifest_id") != "night-voyager.skill-runtime-manifest"
        or runtime_manifest.get("manifest_version") != "1.0.0"
        or runtime_manifest.get("manifest_sha256") != _canonical_json_sha256(runtime_content)
        or runtime_identities != expected_runtime_identities
        or evaluation_manifest.get("manifest_id") != "night-voyager.skill-eval-manifest"
        or evaluation_manifest.get("manifest_version") != "1.0.0"
        or evaluation_manifest.get("manifest_sha256") != _canonical_json_sha256(evaluation_content)
        or evaluation_identities
        != tuple((key, version) for key, version, _ in expected_runtime_identities)
        or seed_identities
        != tuple(
            (key, "1.0.0")
            for key, version, _ in expected_runtime_identities
            if version == "1.0.0"
        )
        or seed_activation_count != 1
    ):
        raise SystemExit("versioned Skill packaged manifest contract drift")

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    adr = (ROOT / SKILL_SURFACE[5]).read_text(encoding="utf-8")
    reference = (ROOT / SKILL_SURFACE[6]).read_text(encoding="utf-8")
    operations = (ROOT / SKILL_SURFACE[7]).read_text(encoding="utf-8")
    migration = (ROOT / SKILL_SURFACE[0]).read_text(encoding="utf-8")
    plan = (
        ROOT / "docs/superpowers/plans/2026-07-16-versioned-skill-runtime-pinning.md"
    ).read_text(encoding="utf-8")
    spec = (
        ROOT / "docs/superpowers/specs/2026-07-16-governed-collaboration-core-design.md"
    ).read_text(encoding="utf-8")
    if (
        "skills-check:" not in makefile
        or workflow.count("make skills-check") != 1
        or "versioned-skills-and-runtime-pins.md" not in docs_index
        or "skill-governance.md" not in docs_index
        or "0009-versioned-skill-runtime-pinning.md" not in docs_index
        or "- Status: Accepted" not in adr
        or "Implementation status: Implemented by migration `0008`" not in adr
        or "exactly five" not in adr
        or "five-field pin" not in adr
        or "catalog_only" not in reference
        or "planning_runtime" not in reference
        or "legacy_unpinned" not in reference
        or "make skills-check" not in operations
        or "make skills-db-check SUITE=lifecycle" not in operations
        or 'revision = "0008"' not in migration
        or 'down_revision = "0007"' not in migration
        or "expected_evaluation_projection jsonb NOT NULL" not in migration
        or "p_result IS DISTINCT FROM version.expected_evaluation_projection"
        not in migration
        or "**Implementation status:** Complete." not in plan
        or "PR A, PR B, and PR C are implemented" not in spec
        or "PR C has not started" in spec
    ):
        raise SystemExit("versioned Skill command, status, or documentation drift")
    print("proof Skill surface: six governed definitions and packaged runtime pins confirmed")


def verify_release_surface() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if pyproject["project"]["description"] != DESCRIPTION:
        raise SystemExit("project description drift")

    readme_contracts = (
        (
            "README.md",
            "Night Voyager turns a synthetic study-abroad comparison",
            "## Engineering proof",
            "## Evaluate the release",
            "## Synthetic and local limits",
            "## Milestones and history",
        ),
        (
            "README_CN.md",
            "Night Voyager 将一组三国留学比较",
            "## 工程证据",
            "## 验证 release",
            "## 合成与本地边界",
            "## Milestone 与历史",
        ),
    )
    for relative, outcome, proof, evaluator, limits, history in readme_contracts:
        source = (ROOT / relative).read_text(encoding="utf-8")
        required = (outcome, *M5_SCREENSHOTS, proof, evaluator, limits, history)
        try:
            positions = [source.index(value) for value in required]
        except ValueError as error:
            raise SystemExit(f"missing {RELEASE_TAG} README contract: {relative}") from error
        if positions != sorted(positions):
            raise SystemExit(f"{RELEASE_TAG} README outcome order drift: {relative}")
        if any(document not in source for document in RELEASE_DOCUMENTS):
            raise SystemExit(f"{RELEASE_TAG} README release links drift: {relative}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README_CN.md").read_text(encoding="utf-8")

    for relative in RELEASE_DOCUMENTS:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"missing {RELEASE_TAG} release document: {relative}")

    for relative, expected_digest in PUBLISHED_RELEASE_DOCUMENTS.items():
        actual_digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise SystemExit(f"published release document drift: {relative}")
    release = (ROOT / RELEASE_DOCUMENTS[0]).read_text(encoding="utf-8")
    try:
        heading_positions = [release.index(heading) for heading in RELEASE_HEADINGS]
    except ValueError as error:
        raise SystemExit(
            f"{RELEASE_TAG} release notes contract missing required heading"
        ) from error
    if heading_positions != sorted(heading_positions):
        raise SystemExit(f"{RELEASE_TAG} release notes heading order drift")
    for index, position in enumerate(heading_positions):
        end = (
            heading_positions[index + 1]
            if index + 1 < len(heading_positions)
            else len(release)
        )
        if re.search(r"[\u4e00-\u9fff]", release[position:end]) is None:
            raise SystemExit(f"{RELEASE_TAG} release notes require Simplified Chinese body")
    if any(token not in release for token in RELEASE_NOTE_TOKENS):
        raise SystemExit(f"{RELEASE_TAG} release notes contract boundary drift")

    how_to = (ROOT / RELEASE_DOCUMENTS[1]).read_text(encoding="utf-8")
    if any(token not in how_to for token in RELEASE_HOW_TO_TOKENS):
        raise SystemExit(f"{RELEASE_TAG} release how-to contract boundary drift")

    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    if any(
        "release/source-archive verification" not in source
        for source in (readme, readme_cn)
    ):
        raise SystemExit("README release/source-archive verification wording drift")
    if "source-archive verification" not in docs_index:
        raise SystemExit("documentation index source-archive verification wording drift")

    stale = ("bootstrap stage", "local bootstrap phase", "no released production version")
    for relative in ("SECURITY.md", "CONTRIBUTING.md", "docs/README.md"):
        source = (ROOT / relative).read_text(encoding="utf-8").lower()
        if any(phrase in source for phrase in stale):
            raise SystemExit(f"stale bootstrap release wording: {relative}")
    print(f"proof release surface: {RELEASE_TAG} local synthetic portfolio contract confirmed")


def package_version(packages: list[dict[str, object]], name: str) -> str:
    for package in packages:
        if package.get("name") == name:
            version = package.get("version")
            if isinstance(version, str):
                return version
    raise SystemExit(f"missing locked package: {name}")


def verify_config() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    npm_lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    constraint = (ROOT / "build-constraints.txt").read_text(encoding="utf-8").strip()

    versions = {
        "pyproject": pyproject["project"]["version"],
        "uv.lock": package_version(uv_lock["package"], "night-voyager"),
        "web/package.json": web_package["version"],
        "web/package-lock.json": npm_lock["packages"][""]["version"],
    }
    if set(versions.values()) != {VERSION}:
        raise SystemExit(f"identity version mismatch: {versions}")
    runtime_dependencies = pyproject["project"]["dependencies"]
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    if optional_dependencies.get("dra") != ["httpx2>=2.5,<2.6"]:
        raise SystemExit("DRA must remain an exact optional dependency range")
    if package_version(uv_lock["package"], "httpx2") != "2.5.0":
        raise SystemExit("httpx2 optional lock must remain at the reviewed 2.5.0 version")
    if optional_dependencies.get("mke") != ["mcp>=1.28.1,<2"]:
        raise SystemExit("MKE must remain an exact optional dependency range")
    if package_version(uv_lock["package"], "mcp") != "1.28.1":
        raise SystemExit("MCP optional lock must remain at the reviewed 1.28.1 version")
    if "fastapi>=0.139,<0.140" not in runtime_dependencies:
        raise SystemExit("FastAPI runtime dependency must remain on approved 0.139.x")
    if "starlette>=1.3.1,<1.4" not in runtime_dependencies:
        raise SystemExit(
            "Starlette runtime dependency must enforce the approved 1.3.1 security floor"
        )
    locked_fastapi = tuple(
        int(part) for part in package_version(uv_lock["package"], "fastapi").split(".")
    )
    if not (FASTAPI_VERSION_FLOOR <= locked_fastapi < FASTAPI_VERSION_CEILING):
        raise SystemExit("FastAPI lock must remain within approved >=0.139.2,<0.140 range")
    locked_starlette = tuple(
        int(part) for part in package_version(uv_lock["package"], "starlette").split(".")
    )
    if not (locked_starlette >= (1, 3, 1) and locked_starlette < (1, 4)):
        raise SystemExit("Starlette lock must remain within the approved >=1.3.1,<1.4 range")
    if pyproject["build-system"]["requires"] != ["hatchling==1.31.0"]:
        raise SystemExit("build backend must be exactly pinned")
    if not constraint.startswith("hatchling==1.31.0 --hash=sha256:"):
        raise SystemExit("build backend constraint must include a SHA-256 hash")
    if constraint.count("--hash=sha256:") != 5:
        raise SystemExit("all build backend dependencies must be hash constrained")
    if POSTGRES_IMAGE not in compose:
        raise SystemExit("Compose PostgreSQL image must use the approved exact tag and digest")
    if re.search(r"(?m)^\s{2}mke:\s*$", compose):
        raise SystemExit("MKE must not become a Compose service")
    post_m4a = sorted((ROOT / "migrations" / "versions").glob("000[56]_*.py"))
    if [path.name for path in post_m4a] != [
        "0005_dra_candidate_promotion.py",
        "0006_governed_mixed_planning.py",
    ]:
        raise SystemExit("post-M4A migration surface must be the governed DRA boundary")
    if "mke" in post_m4a[0].read_text(encoding="utf-8").lower():
        raise SystemExit("M4B must not add a database migration")
    mixed_migration = post_m4a[1].read_text(encoding="utf-8")
    if "down_revision = \"0005\"" not in mixed_migration or "op.create_table" in mixed_migration:
        raise SystemExit("mixed planning migration must follow 0005 without adding a table")
    for required in (
        ROOT / "fixtures/m4b/candidate-artifact-lock.json",
        ROOT / "fixtures/m4b/manifest.json",
    ):
        if not required.is_file():
            raise SystemExit(f"missing M4B public contract: {required.name}")
    for pure_file in (ROOT / "src/night_voyager/evidence").glob("*.py"):
        pure_content = pure_file.read_text(encoding="utf-8")
        if "import mcp" in pure_content or "from mcp" in pure_content:
            raise SystemExit("pure M4B boundary must not import the optional MCP SDK")
    local_bindings = (
        '"127.0.0.1:${POSTGRES_PORT:-55432}:5432"',
        '"127.0.0.1:${API_PORT:-8000}:8000"',
        '"127.0.0.1:${WEB_PORT:-3000}:3000"',
    )
    if not all(binding in compose for binding in local_bindings):
        raise SystemExit("Compose host ports must bind to IPv4 loopback")
    if (ROOT / ".python-version").read_text(encoding="utf-8").strip() != "3.12.13":
        raise SystemExit("Python patch version drift")
    if (ROOT / ".node-version").read_text(encoding="utf-8").strip() != "24.18.0":
        raise SystemExit("Node.js patch version drift")
    print(f"proof identity: Night Voyager package surfaces agree on version {VERSION}")
    print(
        "proof dependencies: FastAPI >=0.139.2,<0.140, "
        "Starlette >=1.3.1,<1.4, "
        "and hashed Hatchling 1.31.0 constraints confirmed"
    )
    print(f"proof compose: exact PostgreSQL reference confirmed ({POSTGRES_IMAGE})")
    print("proof config: Python/Node pins and IPv4-loopback host bindings confirmed")


def verify_wheel() -> None:
    run(
        "uv",
        "build",
        "--wheel",
        "--build-constraints",
        "build-constraints.txt",
        "--require-hashes",
    )
    wheel = max((ROOT / "dist").glob("*.whl"), key=lambda path: path.stat().st_mtime)
    with tempfile.TemporaryDirectory(prefix="night-voyager-wheel-") as temp:
        venv = str(Path(temp) / ".venv")
        run("uv", "venv", venv, "--python", "3.12.13")
        python = f"{venv}/bin/python"
        wheel_install_environment = os.environ.copy()
        wheel_install_environment.pop("UV_REQUIRE_HASHES", None)
        run(
            "uv",
            "pip",
            "install",
            "--python",
            python,
            str(wheel),
            env=wheel_install_environment,
        )
        run(
            python,
            "-c",
            "import sys; from night_voyager.api import create_app; "
            "from night_voyager.skills.registry import SkillRuntimeRegistry; "
            "from night_voyager.skills.evaluation import SkillEvaluator; "
            "registry = SkillRuntimeRegistry.load_packaged(); "
            "evaluator = SkillEvaluator.load_packaged(registry); "
            "assert len(registry.entries) == 7; "
            "assert len(evaluator.manifest.datasets) == 7; "
            f"assert create_app().version == {VERSION!r}; "
            "assert \"httpx2\" not in sys.modules",
        )
    print(f"proof wheel: isolated installed-wheel import and app factory passed ({wheel.name})")


async def verify_database_catalog(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            roles = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolbypassrls
            FROM pg_roles
            WHERE rolname IN (
              'night_voyager_migrator', 'night_voyager_api', 'night_voyager_worker'
            )
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            if len(roles) != 3 or any(
                row["rolsuper"]
                or row["rolcreatedb"]
                or row["rolcreaterole"]
                or row["rolinherit"]
                or row["rolbypassrls"]
                for row in roles
            ):
                raise SystemExit("database roles violate least-privilege attributes")

            tenant_tables = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, r.rolname AS owner
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            JOIN pg_roles AS r ON r.oid = c.relowner
            WHERE n.nspname = 'app' AND c.relkind = 'r'
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            expected_tenant_tables = {
                "organizations",
                "actors",
                "memberships",
            } | (
                M3A_TABLES
                | M3B_TABLES
                | M4A_TABLES
                | DRA_TABLES
                | COLLABORATION_TABLES
                | SKILL_TABLES
            )
            if {row["relname"] for row in tenant_tables} != expected_tenant_tables or any(
                not row["relrowsecurity"]
                or not row["relforcerowsecurity"]
                or row["owner"] != "night_voyager_migrator"
                for row in tenant_tables
            ):
                raise SystemExit("app tenant tables must be migrator-owned with forced RLS")

            policy_count = (
                await connection.execute(
                    text("SELECT count(*) FROM pg_policies WHERE schemaname = 'app'")
                )
            ).scalar_one()
            if policy_count != 38:
                raise SystemExit("every app tenant table requires one explicit policy")

            runtime_writes = (
                await connection.execute(
                    text("""
                    SELECT count(*) FROM information_schema.role_table_grants
                    WHERE table_schema = 'app' AND table_name = ANY(:tables)
                      AND grantee IN ('night_voyager_api','night_voyager_worker')
                      AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
                    """),
                    {
                        "tables": sorted(
                            M3A_TABLES
                            | M3B_TABLES
                            | M4A_TABLES
                            | DRA_TABLES
                            | COLLABORATION_TABLES
                            | SKILL_TABLES
                        )
                    },
                )
            ).scalar_one()
            if runtime_writes:
                raise SystemExit("runtime roles must not have direct application write grants")

            collaboration_runtime_grants = (
                await connection.execute(
                    text("""
                    SELECT count(*) FROM information_schema.role_table_grants
                    WHERE table_schema = 'app' AND table_name = ANY(:tables)
                      AND grantee IN ('night_voyager_api','night_voyager_worker')
                    """),
                    {"tables": sorted(COLLABORATION_TABLES)},
                )
            ).scalar_one()
            if collaboration_runtime_grants:
                raise SystemExit("runtime roles must not access collaboration authority tables")

            skill_runtime_grants = (
                await connection.execute(
                    text("""
                    SELECT count(*) FROM information_schema.role_table_grants
                    WHERE table_schema = 'app' AND table_name = ANY(:tables)
                      AND grantee IN ('night_voyager_api','night_voyager_worker')
                    """),
                    {"tables": sorted(SKILL_TABLES)},
                )
            ).scalar_one()
            if skill_runtime_grants:
                raise SystemExit("runtime roles must not access Skill authority tables")

            app_functions = (
                (
                    await connection.execute(
                        text("""
                        SELECT p.proname,p.prosecdef,p.proconfig,
                          oidvectortypes(p.proargtypes) AS identity_arguments,
                          has_function_privilege('public',p.oid,'EXECUTE') AS public_execute,
                          has_function_privilege(
                            'night_voyager_api',p.oid,'EXECUTE'
                          ) AS api_execute,
                          has_function_privilege(
                            'night_voyager_worker',p.oid,'EXECUTE'
                          ) AS worker_execute
                        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                        WHERE n.nspname='app' AND (p.proname IN
                          ('publish_case_revision','transition_case','persist_source_pack',
                           'persist_evidence_ref','persist_planning_result','review_planning_run',
                           'decide_family_brief','create_agent_task','cancel_agent_task',
                           'claim_agent_task','start_agent_task','heartbeat_agent_task',
                           'fail_agent_task','finalize_agent_task_result')
                           OR p.proname IN
                          ('import_dra_research_candidate','verify_and_promote_dra_candidate',
                           'load_governed_mixed_planning_snapshot')
                           OR p.proname IN
                          ('create_collaboration_thread','append_collaboration_message',
                           'propose_memory_candidate','verify_memory_candidate',
                           'read_collaboration_thread','read_collaboration_messages',
                           'read_memory_candidates','read_confirmed_facts',
                           'seed_demo_collaboration')
                           OR p.proname IN
                          ('create_skill_change_candidate','record_skill_candidate_evaluation',
                           'promote_skill_change_candidate','rollback_skill_activation',
                           'list_skill_catalog','get_skill_catalog_item',
                           'load_skill_candidate_context','inspect_planning_skill',
                           'load_agent_task_skill_pin',
                           'load_persisted_synthetic_planning_snapshot',
                           'seed_demo_skill_registry',
                           'seed_demo_pinned_collaboration_task'))
                        """)
                    )
                )
                .mappings()
                .all()
            )
            expected_app_functions = {
                "publish_case_revision",
                "transition_case",
                "persist_source_pack",
                "persist_evidence_ref",
                "persist_planning_result",
                "review_planning_run",
                "decide_family_brief",
                "create_agent_task",
                "cancel_agent_task",
                "claim_agent_task",
                "start_agent_task",
                "heartbeat_agent_task",
                "fail_agent_task",
                "finalize_agent_task_result",
                "import_dra_research_candidate",
                "verify_and_promote_dra_candidate",
                "load_governed_mixed_planning_snapshot",
                "seed_demo_collaboration",
                "seed_demo_skill_registry",
                "seed_demo_pinned_collaboration_task",
            } | (
                COLLABORATION_API_FUNCTIONS
                | SKILL_API_FUNCTIONS
                | SKILL_WORKER_FUNCTIONS
            )
            if {row["proname"] for row in app_functions} != expected_app_functions or any(
                not row["prosecdef"]
                or row["proconfig"] != ["search_path=pg_catalog, pg_temp"]
                or row["public_execute"]
                for row in app_functions
            ):
                raise SystemExit("app functions violate narrow SECURITY DEFINER contract")
            api_functions = (
                {
                    "transition_case",
                    "persist_source_pack",
                    "persist_evidence_ref",
                    "persist_planning_result",
                    "review_planning_run",
                    "decide_family_brief",
                    "create_agent_task",
                    "cancel_agent_task",
                    "import_dra_research_candidate",
                    "verify_and_promote_dra_candidate",
                }
                | COLLABORATION_API_FUNCTIONS
                | SKILL_API_FUNCTIONS
            )
            worker_functions = {
                "claim_agent_task",
                "start_agent_task",
                "heartbeat_agent_task",
                "fail_agent_task",
                "finalize_agent_task_result",
                "load_governed_mixed_planning_snapshot",
            } | SKILL_WORKER_FUNCTIONS
            worker_signatures = {
                row["proname"]: row["identity_arguments"]
                for row in app_functions
                if row["proname"] in worker_functions
            }
            if worker_signatures["start_agent_task"] != "uuid, uuid, text, bigint, text":
                raise SystemExit("start_agent_task audit signature drift")
            if worker_signatures["fail_agent_task"] != (
                "uuid, uuid, text, bigint, text, boolean, boolean"
            ):
                raise SystemExit("fail_agent_task audit signature drift")
            if worker_signatures["load_governed_mixed_planning_snapshot"] != (
                "uuid, uuid, integer, uuid, integer, text"
            ):
                raise SystemExit("mixed snapshot authority signature drift")
            create_signature = next(
                row["identity_arguments"]
                for row in app_functions
                if row["proname"] == "create_agent_task"
            )
            if create_signature != (
                "uuid, uuid, uuid, uuid, text, integer, uuid, integer, text, jsonb, text, text"
            ):
                raise SystemExit("mixed task creation signature drift")
            collaboration_signatures = {
                row["proname"]: row["identity_arguments"]
                for row in app_functions
                if row["proname"] in COLLABORATION_API_FUNCTIONS
                or row["proname"] == "seed_demo_collaboration"
            }
            if collaboration_signatures != {
                "create_collaboration_thread": "uuid, uuid, text, uuid, uuid, text, text",
                "append_collaboration_message": (
                    "uuid, uuid, text, uuid, uuid, text, text, text, text"
                ),
                "propose_memory_candidate": (
                    "uuid, uuid, text, uuid, uuid, integer, text, jsonb, text, text, text"
                ),
                "verify_memory_candidate": (
                    "uuid, uuid, uuid, integer, text, text, uuid, uuid, text, text"
                ),
                "read_collaboration_thread": "uuid, uuid, text, uuid",
                "read_collaboration_messages": ("uuid, uuid, text, uuid, bigint, integer"),
                "read_memory_candidates": "uuid, uuid, text, uuid, integer",
                "read_confirmed_facts": (
                    "uuid, uuid, text, uuid, integer, text, integer, integer"
                ),
                "seed_demo_collaboration": ("uuid, uuid, uuid, uuid, uuid, uuid, uuid, uuid, text"),
            }:
                raise SystemExit("collaboration authority signature drift")
            skill_signatures = {
                row["proname"]: row["identity_arguments"]
                for row in app_functions
                if row["proname"] in SKILL_API_FUNCTIONS
                or row["proname"] in SKILL_WORKER_FUNCTIONS
                or row["proname"] == "seed_demo_skill_registry"
                or row["proname"] == "seed_demo_pinned_collaboration_task"
            }
            if skill_signatures != {
                "create_skill_change_candidate": (
                    "uuid, uuid, text, uuid, text, text, text, text, jsonb, text, text"
                ),
                "record_skill_candidate_evaluation": ("uuid, uuid, uuid, uuid, jsonb, text, text"),
                "promote_skill_change_candidate": (
                    "uuid, uuid, uuid, uuid, text, bigint, text, jsonb, text, text"
                ),
                "rollback_skill_activation": (
                    "uuid, uuid, text, uuid, text, text, bigint, text, jsonb, text, text"
                ),
                "list_skill_catalog": "uuid, uuid",
                "get_skill_catalog_item": "uuid, uuid, text",
                "load_skill_candidate_context": "uuid, uuid, uuid",
                "inspect_planning_skill": "uuid, uuid, uuid",
                "load_agent_task_skill_pin": "uuid, uuid, bigint",
                "load_persisted_synthetic_planning_snapshot": (
                    "uuid, uuid, integer, uuid, integer, text"
                ),
                "seed_demo_skill_registry": "uuid, uuid, jsonb",
                "seed_demo_pinned_collaboration_task": (
                    "uuid, uuid, uuid, uuid, jsonb"
                ),
            }:
                raise SystemExit("Skill authority signature drift")
            if any(
                (row["proname"] in SKILL_API_FUNCTIONS) != row["api_execute"]
                or (row["proname"] in SKILL_WORKER_FUNCTIONS) != row["worker_execute"]
                for row in app_functions
                if row["proname"] in SKILL_API_FUNCTIONS
                or row["proname"] in SKILL_WORKER_FUNCTIONS
                or row["proname"] == "seed_demo_skill_registry"
                or row["proname"] == "seed_demo_pinned_collaboration_task"
            ):
                raise SystemExit("Skill function grants violate API/worker separation")
            pin_columns = (
                (
                    await connection.execute(
                        text("""
                    SELECT table_name,column_name,data_type,is_nullable
                    FROM information_schema.columns
                    WHERE table_schema='app'
                      AND table_name IN ('agent_tasks','agent_executions')
                      AND column_name IN (
                        'skill_definition_id','skill_version_id',
                        'skill_activation_event_id','skill_activation_sequence',
                        'runtime_binding_sha256'
                      )
                    ORDER BY table_name,column_name
                    """)
                    )
                )
                .mappings()
                .all()
            )
            expected_pin_types = {
                "skill_definition_id": "uuid",
                "skill_version_id": "uuid",
                "skill_activation_event_id": "uuid",
                "skill_activation_sequence": "bigint",
                "runtime_binding_sha256": "text",
            }
            if len(pin_columns) != 10 or any(
                row["data_type"] != expected_pin_types[row["column_name"]]
                or row["is_nullable"] != "YES"
                for row in pin_columns
            ):
                raise SystemExit("five-field task pin catalog drift")
            pin_constraints = (
                (
                    await connection.execute(
                        text("""
                    SELECT conname
                    FROM pg_constraint
                    WHERE conrelid IN ('app.agent_tasks'::regclass,'app.agent_executions'::regclass)
                      AND conname LIKE '%skill%'
                    """)
                    )
                )
                .scalars()
                .all()
            )
            if set(pin_constraints) != {
                "agent_tasks_skill_pin_all_or_none",
                "agent_tasks_skill_version_fk",
                "agent_tasks_skill_activation_fk",
                "agent_tasks_skill_pin_identity_unique",
                "agent_executions_skill_pin_all_or_none",
                "agent_executions_task_skill_pin_fk",
            }:
                raise SystemExit("five-field task pin catalog drift")
            effective_index = await connection.scalar(
                text("SELECT pg_get_indexdef('app.agent_tasks_one_effective_operation'::regclass)")
            )
            if not isinstance(effective_index, str) or any(
                field not in effective_index for field in expected_pin_types
            ):
                raise SystemExit("five-field task pin catalog drift")
            planning_persistence = await connection.scalar(
                text("SELECT pg_get_functiondef(to_regprocedure(:signature))"),
                {
                    "signature": (
                        "app.persist_planning_result("
                        "uuid,uuid,uuid,integer,uuid,integer,text,text,text,text,text,uuid,jsonb)"
                    )
                },
            )
            if not isinstance(planning_persistence, str):
                raise SystemExit("planning result lock order drift")
            case_lock = planning_persistence.find("FROM app.student_cases selected_case_row")
            case_for_update = planning_persistence.find("FOR UPDATE", case_lock)
            planning_run_update = planning_persistence.find(
                "UPDATE app.planning_runs", case_for_update
            )
            if not 0 <= case_lock < case_for_update < planning_run_update:
                raise SystemExit("planning result lock order drift")
            legacy_writer = next(
                row for row in app_functions if row["proname"] == "publish_case_revision"
            )
            if legacy_writer["api_execute"]:
                raise SystemExit("legacy Case revision writer must not be executable by the API")
            if any(
                (row["proname"] in api_functions) != row["api_execute"]
                or (row["proname"] in worker_functions) != row["worker_execute"]
                for row in app_functions
            ):
                raise SystemExit("app function grants violate API/worker separation")

            internal_columns = (
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema='internal' AND table_name='agent_task_dispatch' "
                            "ORDER BY ordinal_position"
                        )
                    )
                )
                .scalars()
                .all()
            )
            if internal_columns != ["task_id", "organization_id", "available_at"]:
                raise SystemExit("internal dispatch column allowlist drift")
            internal_ownership = (
                (
                    await connection.execute(
                        text(
                            "SELECT pg_get_userbyid(c.relowner) AS table_owner, "
                            "pg_get_userbyid(n.nspowner) AS schema_owner "
                            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname='internal' AND c.relname='agent_task_dispatch'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            if dict(internal_ownership) != {
                "table_owner": "night_voyager_migrator",
                "schema_owner": "night_voyager_migrator",
            }:
                raise SystemExit("internal dispatch ownership drift")
            internal_grants = (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE table_schema='internal' AND table_name='agent_task_dispatch' "
                        "AND grantee IN ('PUBLIC','night_voyager_api','night_voyager_worker')"
                    )
                )
            ).scalar_one()
            if internal_grants:
                raise SystemExit("runtime roles must not access internal dispatch storage")
            internal_schema_access = (
                await connection.execute(
                    text(
                        "SELECT has_schema_privilege('night_voyager_api','internal','USAGE') "
                        "OR has_schema_privilege('night_voyager_worker','internal','USAGE')"
                    )
                )
            ).scalar_one()
            if internal_schema_access:
                raise SystemExit("runtime roles must not use the internal schema")

            auth_grants = (
                await connection.execute(
                    text(
                        """
            SELECT count(*) FROM information_schema.role_table_grants
            WHERE table_schema = 'auth'
              AND grantee IN ('night_voyager_api', 'night_voyager_worker')
            """
                    )
                )
            ).scalar_one()
            if auth_grants:
                raise SystemExit("runtime roles must not have direct auth table grants")

            functions = (
                (
                    await connection.execute(
                        text(
                            """
            SELECT p.oid, p.proname, p.prosecdef, p.proconfig,
                   has_function_privilege('public', p.oid, 'EXECUTE') AS public_execute,
                   has_function_privilege('night_voyager_api', p.oid, 'EXECUTE') AS api_execute,
                   has_function_privilege(
                       'night_voyager_worker', p.oid, 'EXECUTE'
                   ) AS worker_execute
            FROM pg_proc AS p
            JOIN pg_namespace AS n ON n.oid = p.pronamespace
            WHERE n.nspname = 'auth'
            """
                        )
                    )
                )
                .mappings()
                .all()
            )
            expected = {
                "mint_demo_session",
                "resolve_demo_session",
                "rotate_demo_session",
                "revoke_demo_session",
                "resolve_demo_session_with_csrf",
            }
            if {row["proname"] for row in functions} != expected or any(
                not row["prosecdef"]
                or row["proconfig"] != ["search_path=pg_catalog, pg_temp"]
                or row["public_execute"]
                or not row["api_execute"]
                or row["worker_execute"]
                for row in functions
            ):
                raise SystemExit("auth functions violate SECURITY DEFINER privilege contract")
    finally:
        await engine.dispose()
    print("proof database: role, forced-RLS, policy, auth grant, and function catalog passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tree-mode", choices=("development", "release", "snapshot"), default="development"
    )
    parser.add_argument("--check-db-roles", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.check_db_roles:
        database_url = os.environ.get("NIGHT_VOYAGER_MIGRATION_DATABASE_URL")
        if not database_url:
            raise SystemExit("NIGHT_VOYAGER_MIGRATION_DATABASE_URL is required")
        asyncio.run(verify_database_catalog(database_url))
        return
    verify_tree_mode(args.tree_mode)
    verify_public_hygiene()
    verify_m5_public_evidence()
    verify_dra_surface()
    verify_collaboration_surface()
    verify_skill_surface()
    verify_release_surface()
    verify_config()
    verify_wheel()


if __name__ == "__main__":
    main()
