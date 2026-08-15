# Night Voyager

Night Voyager helps study-abroad advisors turn confirmed facts, route analysis, advisor review, and client confirmation into an evidence-grounded decision workflow with a persisted receipt and timeline.

## Advisor workspace overview

![Advisor workspace overview](docs/assets/advisor-workspace-overview.png)

This real Chromium frame shows the current local synthetic, provider-free advisor workspace in a static route-analysis state. It is review evidence, not production or admissions-outcome proof. The [showcase manifest](docs/evidence/advisor-showcase-manifest.json) records the source commit/tree, route/state, viewport, locale, and SHA-256 for all canonical assets.

## Who it is for and the real problem

For study-abroad advisors comparing Japan, Malaysia, and Australia with a student/client. The real problem is keeping facts, route reasoning, approval state, and the final decision inspectable when assumptions or budget change; generating another untraceable recommendation is not enough.

## Five-stage workflow

1. **Confirm facts:** keep source-backed facts and assumptions explicit.
2. **Analyze routes:** compare eligible routes against the confirmed constraints.
3. **Advisor review:** let the advisor approve, revise, or stop the proposed plan.
4. **Client confirmation:** record the client’s explicit confirmation as a separate authority step.
5. **Persist the outcome:** issue a receipt and TimelinePlan that can be inspected later.

## Normal path and blocked recovery

![Advisor normal path](docs/assets/advisor-normal-path.png)

The normal frame shows the connected same-Case path through advisor review and client confirmation to the persisted receipt and TimelinePlan.

![Advisor blocked recovery](docs/assets/advisor-blocked-recovery.png)

The blocked frame is an independently seeded deterministic execution scenario: a premise or budget change blocks the checkpoint, and the workflow hands back to advisor reassessment or a safe stop. It does not imply a connected Case or a production outcome.

![Advisor workspace on mobile](docs/assets/advisor-workspace-mobile.png)

The mobile frame is the same real route-analysis workspace at the canonical `390x844` viewport. All four frames are local synthetic, provider-free Chromium evidence.

## Three engineering judgments

- **Durable facts versus live events:** confirmed facts and the receipt/timeline are persisted records; progress and recovery events remain a separate live execution seam.
- **Explicit execution and recovery:** each turn moves through step, model/tool result, and a deterministic stop or recovery boundary that can be inspected.
- **Capabilities versus authority:** capability providers and consumers meet through explicit boundaries, while approval and sandbox constraints keep agent output untrusted until advisor/client authority is applied.

## Quickstart, architecture, and release

- **Quickstart:** run `make help`, `make doctor`, `make demo`, and `make proof`; then open `http://127.0.0.1:3000/`.
- **Architecture:** read the [architecture and milestone history](DESIGN.md) and the [documentation index](docs/README.md).
- **Release:** the [v0.1.5 release notes](docs/releases/v0.1.5.md) and [release verification guide](docs/how-to/verify-v0.1.5-release.md) describe the current released local synthetic baseline; this showcase is presentation-only and release-neutral.

## Detailed proof

The current runtime, contracts, authority boundaries, and release evidence remain below. Historical visual assets are retained for proof and context, but are no longer the README first layer.

The current development candidate remains an AI collaboration platform for study-abroad advisors. The current development candidate presents the reference-driven advisor-centered root and three demo routes through one shared workspace shell as static, local synthetic, provider-free presentation evidence; it is not released or deployed. Stable v0.1.5 remains the prior local synthetic portfolio release. The root performs no API, session, task, or EventSource work.

The complete governed walkthrough begins at `/demo/collaboration` and continues the same Case through `/demo`; the connected same-Case proof ends at the receipt and TimelinePlan. `/demo/plan` is an independent deterministic execution scenario with separately seeded Happy / Blocked paths and does not carry the connected Case or session forward. Screenshots are review evidence, not functional authority; semantic assertions remain the acceptance authority.

<details>
<summary>Historical visual proof captures</summary>

![Chinese-first Night Voyager portfolio entry](docs/assets/night-voyager-portfolio-entry.png)

![Advisor Ledger at review-required](docs/assets/m5-advisor-ledger.png)

![Client confirmation receipt and TimelinePlan](docs/assets/m5-family-receipt-timeline.png)

![Governed collaboration confirmed fact](docs/assets/collaboration-confirmed-fact.png)

![Planning revision comparison and renewed review](docs/assets/night-voyager-planning-revision.png)

Governed plan-execution development evidence (synthetic review evidence only): [current action](docs/assets/plan-execution-current-action.png), [advisor review](docs/assets/plan-execution-advisor-review.png), [mobile reassessment](docs/assets/plan-execution-reassessment-mobile.png), and [mobile recovery](docs/assets/plan-execution-recovery-mobile.png). Semantic assertions remain the acceptance authority; screenshots are review evidence, not functional authority.

</details>

## Engineering proof

- **PostgreSQL and forced RLS:** tenant-scoped runtime roles read and mutate through narrow authority paths backed by the released graph `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007 -> 0008 -> 0009 -> 0010 -> 0011 -> 0012 -> 0013 -> 0014 -> 0015`; the v0.1.5 identity is fixed at migration `0015`.
- **Durable task and SSE:** an `AgentTask` survives worker/API restarts, uses bounded leases and generation fencing, and resumes an authorized event stream.
- **Human gates:** deterministic evidence policy, advisor review, and explicit family confirmation remain separate authorities; model or adapter output cannot promote itself.
- **Governed DRA mixed planning:** an optional offline proof imports only `UNTRUSTED_CANDIDATE` rows, keeps assigned-advisor verification and promotion in one atomic database gate, and materializes one governed mixed PlanningRun through the existing durable worker. The current provider-free prerequisite pins new strict work to exact post-release commit `01ba21f2996769e68cbc88f4bb0596740df27f6b` and `generic-strict-citation@1`; it is not part of the DRA v0.1.6 release.
- **Governed collaboration authority:** the v0.1.2 release separates shared `MessageEvent` communication, typed `MemoryCandidate` proposals, assigned-advisor verification, and atomic versioned `ConfirmedFact` publication.
- **Versioned Skill runtime:** the v0.1.2 release governs an exact six-key catalog, deterministic evaluation, owner activation/rollback, five-field task/execution pins, and pre-start packaged-registry validation.
- **Explicit fact-to-plan authority:** v0.1.3 migration `0009` makes the first deterministic task creation the atomic `intake -> planning` authority with the pinned task, dispatch, first event, and idempotency result; legacy runtime transition authority stays revoked.
- **Browser to database:** v0.1.3 `/demo/collaboration` hands the confirmed same Case to `/demo` without creating a task; the advisor then explicitly starts the real pinned task, SSE, review, parent decision, receipt, and timeline path. The provider-free chain runs in real Chromium against PostgreSQL, while both routes remain independently usable.
- **Planning revision journey:** v0.1.4 releases provider-free `request revision`, a controlled student preferred-country change, retained predecessor lineage, a successor PlanningRun, deterministic old/new comparison, fresh advisor authorization, and only the current family decision. The blocked budget counterfactual reaches neither approval nor decision.
- **Governed timeline execution:** v0.1.5 releases a provider-free `/demo/plan` vertical, closed Happy/Blocked scenarios, structured family attestations, assigned-advisor verification, immutable receipt recovery, PostgreSQL-owned risk/date authority, a reassessment stop, and a bilingual responsive/action-hierarchy proof. It creates no new `AgentTask`, provider call, successor business row, or deployment.
- **Portfolio and dependency boundary:** v0.1.5 includes the frontend dependency maintenance merged in PR #78. Current development now uses Next.js and `eslint-config-next` `16.3.0`; Next.js resolves optional/transitive `sharp 0.35.3`, outside `GHSA-f88m-g3jw-g9cj`, with `postcss@8.5.23` and compatible transitive `nanoid@3.3.18`. The repository has no direct `sharp`, `postcss`, or `nanoid` dependency and no override. The immutable v0.1.5 release was not an audit-zero claim; this current-development wording does not rewrite its historical release evidence. Fresh full and runtime/omit-dev npm audits report zero advisory objects, including no sharp advisory object. Dependabot #7 hosted alert status is evaluated after merge; this local change makes no hosted alert claim. Recovery triggers are public deployment, an untrusted image path, or an advisory change.
- **Complementary-evidence Slice 0 status:** Slice 0 permanently ended as local `evaluation_invalid` safe stop. It has no `MkeCaptureArtifactV2`, Slice 0 terminal receipt, information-gain conclusion, candidate persistence, Slice 1/2 work, or v0.1.6 release. PR #87 is merged; hosted CI and publication cleanup are complete, and no later stage was unlocked.

## Evaluate the release

Evaluators need Docker Desktop, Docker Compose, and GNU Make:

```bash
make help
make doctor
make demo
make proof
make down
```

Open `http://127.0.0.1:3000/` for the advisor workspace entry. It server-renders in exact `zh-CN`; use the labelled `中文` / `English` control to select exact `en`. The presentation-only preference is stored at `night-voyager:presentation-locale:v1` and never enters the session journey, HTTP/BFF requests, task, SSE, or domain authority. For the connected same-Case proof, follow the [collaboration runbook](docs/operations/collaboration-walkthrough.md) from `/demo/collaboration` into `/demo`. For the independent deterministic execution scenario, use the [execution walkthrough](docs/operations/plan-execution-walkthrough.md) at `/demo/plan`. The [v0.1.5 release/source-archive verification guide](docs/how-to/verify-v0.1.5-release.md) defines the current release gates.

For the current same-Case development walkthrough, begin at `/demo/collaboration`,
confirm the synthetic family fact, choose `继续进入规划` (`Continue to planning` in
English), and use the explicit task action on `/demo`. The handoff itself
performs read-only validation and creates no task.

The current focused planning-revision proof uses
`NIGHT_VOYAGER_COMPOSE_PROOF_MODE=planning-revision`. Screenshot maintenance is
explicitly separated: `UPDATE_PORTFOLIO_SCREENSHOTS` updates the current
development-candidate portfolio captures, while `UPDATE_PLANNING_REVISION_SCREENSHOT` may update only
`night-voyager-planning-revision.png`.

For the governed execution path released in v0.1.5, open `/demo/plan` and follow
the [plan execution walkthrough](docs/operations/plan-execution-walkthrough.md).
PR #80, PR #83, PR #84, and PR #85 are merged and included in released v0.1.5;
the release contains the governed authority, recovery/reassessment closure,
reconciliation, and professional presentation/evaluator-first DX. PR #87 is merged;
its hosted CI and publication cleanup are complete.

`make doctor` checks Docker, Compose capability, local ports, at least 5 GiB on the host project filesystem, and at least 8 GiB on the Docker VM filesystem. Operators may override only the Docker VM threshold with `NIGHT_VOYAGER_DOCKER_MINIMUM_KB`; the check fails closed and never removes Docker resources. `make demo` migrates and seeds a fresh synthetic stack. `make proof` verifies configuration, public hygiene, and an isolated installed wheel without requiring host Python, uv, Node.js, or npm. `make compose-proof` additionally exercises the browser-to-database flow in real Chromium.

## Synthetic and local limits

- v0.1.5 is a local synthetic portfolio release with the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and professional evaluator-facing presentation. It is not a production deployment or tenancy claim.
- The repository contains no real student records and makes no admissions outcome, real-user, SLA, availability, or business-impact claim.
- The worker and SSE evidence is deterministic local proof, not distributed high availability.
- Live DRA, OpenClaw, remote providers, messaging, and product-path MKE are not connected. Deterministic offline DRA candidate import and atomic promotion are implemented locally; governed mixed PlanningRun generation is implemented locally through the existing durable worker. Two separately authorized bounded live attempts returned 25 and 83 same-run Evidence rows, all `uncited`, and both stopped before candidate import. No third provider attempt is authorized; strict live acceptance remains incomplete. M4B remains an optional read-only compatibility adapter whose projections are `UNTRUSTED_CANDIDATE`.
- PR 1, PR 2, and PR 3 of the planning-revision work are released in v0.1.4 as controlled provider-free evidence only. They preserve the failed 25 and 83 row attempts as zero cited rows; strict live acceptance remains incomplete and there is no third provider attempt.
- Governed collaboration PR A, versioned Skill governance PR B, and browser walkthrough/inspector PR C are released in v0.1.2 as local synthetic capabilities. `/demo/collaboration` itself creates no `AgentTask`; only the explicit action after the same-Case handoff to `/demo` starts the existing governed planning path.
- The v0.1.5 release does not add live providers, production deployment, distributed HA, SLA, real student data, real school coverage, advisor-team adoption, admissions outcomes, or business-benefit claims.
- Governed timeline-execution PR A/B/C is released only as local synthetic,
  provider-free evidence; no deployment, live provider, real-user, or outcome
  claim is made.

## Milestones and history

- [v0.1.5 release notes](docs/releases/v0.1.5.md)
- [v0.1.4 historical release notes](docs/releases/v0.1.4.md)
- [v0.1.3 historical release notes](docs/releases/v0.1.3.md)
- [v0.1.2 historical release notes](docs/releases/v0.1.2.md)
- [v0.1.1 historical release notes](docs/releases/v0.1.1.md)
- [v0.1.0 historical release notes](docs/releases/v0.1.0.md)
- [Architecture and milestone history](DESIGN.md)
- [Documentation index](docs/README.md)
- [Connected demo storyboard](docs/design/demo-storyboard.md)
- M5 connected advisor-to-family demo: implemented as the local synthetic walkthrough documented in the [runbook](docs/operations/connected-demo.md).
- [M4B optional read-only MKE candidate proof](docs/operations/mke-candidate-proof.md); outputs remain `UNTRUSTED_CANDIDATE`.
- [Governed DRA mixed-evidence proof](docs/operations/dra-consumer-proof.md); candidate import, atomic human promotion, and governed mixed PlanningRun generation are implemented as a deterministic local closure. The connected synthetic `/demo` remains unchanged.
- [Governed collaboration and confirmed-fact reference](docs/reference/collaboration-and-confirmed-facts.md), [authority runbook](docs/operations/collaboration-authority.md), and [browser walkthrough](docs/operations/collaboration-walkthrough.md); PR A and PR C are released in v0.1.2 as authority and presentation layers.
- [Versioned Skills and runtime pins](docs/reference/versioned-skills-and-runtime-pins.md) and [Skill governance runbook](docs/operations/skill-governance.md); PR B is released in v0.1.2, and PR C renders its read-only server projection.
- [Governed fact-to-plan walkthrough](docs/operations/collaboration-walkthrough.md) and [connected continuation](docs/operations/connected-demo.md); the same confirmed Case now reaches explicit deterministic planning locally without a provider.

## Contributor lane

Contributors additionally need Python 3.12.13 managed by [uv](https://docs.astral.sh/uv/), Node.js 24.18.0, and npm:

```bash
make doctor MODE=dev
make check
make db-check
make collaboration-check
make skills-check
make dra-check
make mke-check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). A Chinese version is available in [README_CN.md](README_CN.md).

## License

MIT
