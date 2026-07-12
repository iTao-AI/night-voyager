from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from night_voyager.planning.models import (
    EvidenceAuthority,
    EvidenceRef,
    PlanningInput,
    RouteCandidate,
    RouteOutcome,
)
from night_voyager.planning.policy import evaluate_planning_run

DEFAULT_MANIFEST = Path("fixtures/m3a/manifest.json")


def validate_planning_fixture(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, str]:
    payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, Any]] = {}
    root = manifest_path.parent.resolve()
    for entry in payload["entries"]:
        path = (root / entry["path"]).resolve()
        if root not in path.parents:
            raise ValueError("source path escapes manifest root")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"source hash mismatch: {entry['id']}")
        entries[entry["id"]] = entry

    routes: list[RouteCandidate] = []
    for route in payload["routes"]:
        entry = entries[route["source_entry_id"]]
        evidence = tuple(
            EvidenceRef(
                schema_version=1,
                evidence_id=f"{route['route_id']}-{claim}",
                claim=claim,
                source_pack_version=payload["source_pack_version"],
                source_entry_id=entry["id"],
                source_sha256=entry["sha256"],
                authority=EvidenceAuthority.ACCEPTED_SYNTHETIC_DEMO,
            )
            for claim in route["claims"]
        )
        routes.append(
            RouteCandidate(
                route_id=route["route_id"],
                outcome=RouteOutcome(route["outcome"]),
                required_claims=tuple(route["required_claims"]),
                evidence=evidence,
            )
        )
    result = evaluate_planning_run(
        PlanningInput(
            schema_version=payload["schema_version"],
            organization_id=payload["organization_id"],
            case_revision=payload["case_revision"],
            source_pack_version=payload["source_pack_version"],
            routes=tuple(routes),
        )
    )
    snapshot: dict[str, str] = {route.route_id: route.outcome.value for route in routes}
    snapshot["run_state"] = result.state.value
    if snapshot != payload["expected"]:
        raise ValueError("planning snapshot does not match expected assertions")
    return snapshot
