from __future__ import annotations

import json
import urllib.request
from http.cookiejar import CookieJar

ORIGIN = "http://127.0.0.1:3000"
API = "http://127.0.0.1:8000/api/v1"
CASE = "40000000-0000-0000-0000-000000000001"
RUN = "70000000-0000-0000-0000-000000000001"
AUSTRALIA = "71000000-0000-0000-0000-000000000001"


def session(role: str) -> tuple[urllib.request.OpenerDirector, str]:
    cookies = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    with opener.open(
        urllib.request.Request(f"{API}/demo/session-bootstrap", headers={"Origin": ORIGIN})
    ) as response:
        bootstrap = json.load(response)
    request = urllib.request.Request(
        f"{API}/demo/sessions",
        data=json.dumps({"demo_actor": role}).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": bootstrap["csrf_token"],
        },
        method="POST",
    )
    with opener.open(request) as response:
        minted = json.load(response)
    return opener, minted["csrf_token"]


def post(
    opener: urllib.request.OpenerDirector,
    path: str,
    csrf: str,
    key: str,
    payload: dict[str, object],
) -> dict[str, object]:
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "X-CSRF-Token": csrf,
            "Idempotency-Key": key,
        },
        method="POST",
    )
    with opener.open(request) as response:
        return json.load(response)


def main() -> None:
    advisor, advisor_csrf = session("advisor")
    approval = post(
        advisor,
        f"/cases/{CASE}/advisor-reviews",
        advisor_csrf,
        "compose-advisor-approval",
        {
            "schema_version": 1,
            "planning_run_id": RUN,
            "expected_case_revision": 1,
            "action": "approve_for_consultation",
            "eligible_route_ids": [AUSTRALIA],
            "risk_acceptances": [],
        },
    )
    brief_id = approval["brief_id"]
    parent, parent_csrf = session("parent")
    with parent.open(f"{API}/decision-briefs/{brief_id}") as response:
        brief = json.load(response)
    routes = brief["family_safe_projection"]["routes"]
    malaysia = next(route for route in routes if route["country"] == "malaysia")
    if malaysia["outcome"] != "blocked" or AUSTRALIA not in brief["family_safe_projection"][
        "eligible_route_ids"
    ]:
        raise SystemExit("compose M3B Brief eligibility projection mismatch")
    decision = post(
        parent,
        f"/decision-briefs/{brief_id}/family-decisions",
        parent_csrf,
        "compose-parent-decision",
        {
            "schema_version": 1,
            "expected_brief_version": 1,
            "selected_route_id": AUSTRALIA,
            "accepted_budget_min_minor": 30_000_000,
            "accepted_budget_max_minor": 40_000_000,
            "currency": "CNY",
            "accepted_trade_offs": ["budget_elasticity"],
        },
    )
    with parent.open(f"{API}/decision-briefs/{brief_id}") as response:
        persisted = json.load(response)
    if persisted["receipt"]["receipt_id"] != decision["receipt_id"]:
        raise SystemExit("compose M3B receipt did not persist")
    if persisted["timeline_id"] != decision["timeline_id"]:
        raise SystemExit("compose M3B timeline did not persist")
    print("compose-proof: M3B advisor-to-parent decision flow passed")


if __name__ == "__main__":
    main()
