# AGENTS.md

This file defines how Codex works in the Night Voyager repository.

## Project purpose

Night Voyager is an evidence-grounded study-abroad decision workflow platform. It is designed as a SaaS-ready portfolio product: the first milestone must be locally runnable and demonstrable, while the architecture should leave a credible path toward multi-tenant deployment.

The P0 product story is intentionally narrow:

- A student and family compare Japan, Malaysia, and Australia.
- Source material enters through explicit manifests and remains traceable.
- Deterministic policy gates decide whether evidence and routes are eligible.
- An advisor reviews the draft before a family-facing decision brief is issued.
- A family decision produces a receipt and timeline rather than an untraceable chat answer.
- A durable background task and SSE progress stream prove the Agent execution seam.

P0 is a controlled local pilot with synthetic data. It is not a claim of production adoption, live institutional coverage, or automated admissions advice.

## Canonical identity

Use these values consistently:

- Product name: `Night Voyager`
- Repository/distribution name: `night-voyager`
- Python package: `night_voyager`
- Web package: `@night-voyager/web`
- Environment variable prefix: `NIGHT_VOYAGER_`
- Default Compose project: `night-voyager`
- Default local ports: web `3000`, API `8000`, PostgreSQL `55432`
- License: MIT

Do not introduce aliases or revive earlier working names.

## Product boundaries

Night Voyager is a decision workflow, not a generic chat recommender. The following are outside P0 unless an approved design explicitly changes scope:

- Public registration, billing, CRM, or production tenancy operations.
- Live application submission or claims of admissions outcomes.
- Automatic advisor approval, evidence promotion, or family decision.
- A second orchestration framework for the same workflow.
- A hard dependency on a paid model, remote Agent, or third-party messaging service.
- Redis, Celery, Temporal, Kafka, Kubernetes, or distributed infrastructure without demonstrated need.
- Emotional-companion positioning or open-ended high-cost conversation promises.

OpenClaw may become a message-channel gateway. DRA may become a research provider. MKE may become a multimodal evidence locator. These systems are adapters behind Night Voyager-owned contracts; none of them owns product authority.

## Source of truth

When sources disagree, use this order:

1. Executable code, tests, migrations, configuration, and commands.
2. Accepted Architecture Decision Records under `docs/decisions/`.
3. Current architecture, design, and reference documentation.
4. Active approved specs and implementation plans.
5. Operations, evidence, and release records.
6. Issue, PR, external note, and historical planning context.

Completed plans explain history but do not override current behavior. If implementation and long-lived documentation disagree, verify the implementation and update the stale document in the same change when appropriate.

Treat the current release entry point as current public guidance and older tagged
release records as immutable history. Do not infer current behavior from an older
release document.

## Read before changing

Always read:

- This file.
- `git status` and the relevant diff.
- The code, tests, and docs directly affected by the task.

Then read only the surfaces relevant to the change:

- Domain or policy: architecture docs, relevant ADRs, policy tests, and state-machine references.
- Database, tenancy, or RLS: migrations, actor-context contract, security tests, and data model references.
- API or BFF: HTTP reference, schema definitions, and contract tests.
- Worker, lease, or SSE: task-state reference, worker implementation, and concurrency tests.
- Frontend or visual system: `DESIGN.md`, product-flow docs, and affected components.
- Public claim or proof: the generating command, manifest, and evidence artifact.

If an ADR, spec, plan, design, or reference document named by this file does not currently exist, report the missing document explicitly. Use the current code, tests, configuration, and commands as the basis for the task; do not invent the missing document's contents or completion status.

Do not load the entire repository or repeat a full planning workflow for a local, reversible edit.

## Domain vocabulary

Prefer the approved domain model and keep terms stable:

- `Organization`
- `ActorContext`
- `StudentCase`
- `SourceManifest`
- `EvidenceRef`
- `PlanningRun`
- `AdvisorReview`
- `DecisionBrief`
- `FamilyDecision`
- `DecisionReceipt`
- `TimelinePlan`
- `AgentTask`
- `SkillVersion`

New names should describe a real new concept, not duplicate an existing one.

## Architecture boundaries

The intended dependency direction is:

```text
Browser -> Next.js BFF -> FastAPI -> application services / ports
                                -> pure domain and policy
                                -> PostgreSQL
Worker  -> task contracts      -> adapters
```

Preserve these rules:

- Domain and deterministic policy code must remain independent of FastAPI, SQLAlchemy, Next.js, and concrete Agent SDKs.
- Product-owned DTOs and ports form the boundary to external Agents and tools.
- PostgreSQL is the business system of record. API and worker roles must not bypass tenant isolation.
- Tenant identity comes from trusted server-side `ActorContext`, never from model output or an untrusted request field.
- Authorization, evidence gates, state transitions, date arithmetic, route eligibility, and approval rules are deterministic code.
- LLMs and Agents may research, draft, summarize, and explain; they may not grant authority or silently change facts.
- External output is untrusted candidate material until schema validation, provenance checks, deterministic policy, and required human review succeed.
- Background task claims use durable PostgreSQL state and bounded leases. P0 does not need a separate queue product.
- Architecture-boundary changes require an ADR in the same change.

P0 must support fake or deterministic adapters so the complete demo and CI do not require remote credentials.

## Evidence and human gates

Every material recommendation must be traceable to accepted evidence or clearly marked as an assumption, comparison, or unresolved risk.

The minimum promotion path is:

```text
source manifest
  -> candidate evidence
  -> path and provenance validation
  -> deterministic eligibility gate
  -> advisor review when required
  -> family-facing brief
  -> explicit family decision and receipt
```

Never implement automatic promotion merely because a model or Agent reports high confidence. Synthetic fixtures and demonstrations must be visibly labelled as synthetic.

## Development Roles And Reasoning Effort

Use the current Sol model configured for the workspace, with only `max`, `high`, and `low`:

- `max`: project-owner conversations, PRD and design, architecture and implementation
  plans, consequential tradeoffs, delivery coordination, and final acceptance.
- `high`: complex implementation, root-cause investigations, deep code review,
  and computer or browser operations.
- `low`: routine implementation, fixes with an identified cause, tests, and mechanical
  documentation work when the scope is clear and the result is easy to verify.

Select effort by the assigned responsibility and risk, not the output's file format;
acceptance standards stay the same. The owner conversation keeps its configured effort;
explicitly assign the model and effort for each new worker. Delegation is optional.

## Risk-based execution

Use the lightest process that still produces trustworthy evidence:

- Level 1 — wording, docs, styling, or a local reversible change: inspect the affected files, make the focused change, and run focused checks.
- Level 2 — behavioral feature or bug fix: use TDD, run focused and relevant broader tests, update affected docs, and use an isolated branch/worktree when the change is substantial.
- Level 3 — architecture, public contract, tenancy/security, migration, or multi-PR change: work from an approved spec/plan, use an isolated branch/worktree, record durable decisions, and run full verification plus review.

Do not make `autoplan`, a second-model review, subagents, repeated full-repository review, or heavyweight artifacts mandatory for every task. Use them only when the user asks or the change's actual risk justifies them.

### Approved design and execution

- Use the official `gstack-workflows` plugin for relevant design and review work, and Superpowers
  for implementation, debugging, and verification; select only the current phase's method.
- Read the current Skill instructions before use. Handoffs include the relevant
  Skill names and entry points; each worker loads the Skills needed for its task.
  Briefly identify the chosen method in the existing progress or return.
- Accept a public-neutral brief or approved repository spec with scope, constraints, observable
  acceptance, delivery owner, Git starting point, and authorization. Use the persistence rules
  below; small work needs only a brief. Directory placement alone is not approval.
- Reuse approved design, verify current rules and Git state, and use
  `superpowers:writing-plans` only for implementation gaps. The delivery owner decides in-scope
  details; changes to goals, key design, acceptance, or authorization return to the design owner.
- When implementation is authorized, the handoff states whether the delivery owner
  may review and decide in-scope plan details; do not infer this from a spec's directory.
- Verify rules in the actual execution worktree; another checkout's update does not
  update this one. Route unresolved approval decisions to the designated coordinating
  owner when present, and reuse existing authorization within its scope.
- Choose direct execution for small work, or one plan route: `superpowers:executing-plans` for
  self-implementation, or `superpowers:subagent-driven-development` for managed implementation
  and review. Do not restart the full manager workflow inside a task worker.
- Return the exact HEAD and acceptance evidence with remaining work. Distinguish local completion
  from hosted delivery; missing remote authorization does not prevent a reviewable local result.

## Design and planning records

Persist an approved design or plan when the change introduces a public contract, crosses multiple modules, changes architecture, or is expected to span multiple PRs.

- Long-lived decisions: `docs/decisions/`
- Approved feature specs: `docs/superpowers/specs/`
- Approved implementation plans: `docs/superpowers/plans/`
- Product and visual direction: `DESIGN.md` and `docs/design/`

Keep public project documents product-neutral. Do not copy private planning material, personal context, private machine paths, or raw planning-system artifacts into this repository.

Keep active plan status and checklists current as implementation progresses. Mark
completed plans explicitly. `docs/README.md` must distinguish implemented,
approved-but-not-implemented, historical, and superseded work.

Published release notes and verification guides are immutable historical records.
Create a new versioned record for a later release and update the current-release entry
point instead of repurposing an older release document.

## Documentation structure

Use Diataxis-style documentation where it helps users find answers:

- `README.md` / `README_CN.md`: product entry and quick start.
- `docs/tutorials/`: learning-oriented end-to-end guides.
- `docs/how-to/`: task-oriented instructions.
- `docs/reference/`: exact API, schema, state, and configuration contracts.
- `docs/explanation/`: architecture and design rationale.
- `docs/decisions/`: accepted ADRs.
- `docs/design/`: product flow and visual-system detail.
- `docs/operations/`: local operation, troubleshooting, and runbooks.
- `docs/evidence/`: reproducible proof manifests and reports.
- `docs/releases/`: release notes when releases exist.

Do not create empty documentation folders. Update docs with the code whenever API, configuration, architecture, domain semantics, setup, demo flow, or user-visible behavior changes.

Every release PR must run the GStack `document-release` targeted audit before merge
(`gstack-workflows:document-release`). Apply the same targeted audit to important features,
public-contract changes, and architecture changes. Check reference, how-to,
explanation, and tutorial coverage according to actual user need; verify commands,
relative links, and discoverability from the README or docs index.

Invoking a Skill does not authorize push, PR mutation, merge, tag, GitHub Release, publish,
or deploy actions; each still requires the repository's explicit user authorization.

Use `document-generate` only to close a concrete, in-scope documentation gap confirmed by
the audit (`gstack-workflows:document-generate`). Do not generate every Diataxis quadrant mechanically or duplicate existing
material. For an internal change with no documentation effect, record
`No documentation impact` in the PR.

## Implementation and testing

- Write a failing test before behavioral implementation; documentation-only changes do not require a TDD cycle.
- Every bug fix needs a regression test that demonstrates the failure.
- Prefer pure functions for deterministic policy and state transitions.
- Keep remote-provider tests mocked in required CI. Real-provider checks are opt-in and separately documented.
- Reuse verification when its inputs have not changed; documentation-only edits do
  not repeat runtime checks. Before another authorized costly run, establish the
  prior failure's cause and usable diagnostics; changing the harness does not reset
  failure of the same goal. Scripted provider tests do not prove live model quality.
- After a second substantive failure of the same real/costly acceptance goal,
  stop those runs and return to the coordinating owner for a route decision.
  An explicitly frozen stage requires an explicit instruction to resume.
- Test tenant isolation and RLS with roles that match runtime behavior, not only a database owner.
- Cover contracts, invalid transitions, lease expiry/reclaim, idempotency, path validation, and evidence-boundary failures.
- Avoid speculative dependencies. Add a library only when it removes meaningful risk or complexity, and document why it is needed.

M0 established these stable repository commands:

```bash
make doctor MODE=dev
make check
make demo
make proof
```

Report command success only when the command exists and has actually passed in the environment being described.

## Git workflow

- The initial rules-first commit on `main` is the repository seed exception.
- After that seed exception, every change intended to enter `main` must be merged through a pull request.
- Subsequent implementation should use a short-lived `codex/` branch, normally in an isolated worktree for substantial work.
- Inspect status before editing and preserve unrelated user changes.
- Stage exact paths; do not use `git add .` or `git add -A`.
- Keep commits reviewable and aligned with one coherent outcome.
- Local commits are normal task completion after verification and diff review.
- Write PR titles in concise English Conventional Commit style unless the user explicitly requests otherwise.
- Write PR descriptions in Simplified Chinese by default for efficient local review, while keeping section headings, commands, code identifiers, API names, CLI output, file paths, and public product terms in English. Use English throughout only when the PR explicitly targets external collaborators or the user requests it.
- Explain the problem, resulting behavior, actual verification and material limits;
  scale detail to the change. Headings and checkbox style are not extra merge gates.
- After creating or updating a PR, read back its persisted title, body, base, head, and
  draft state. Use checkboxes only for genuine pending merge gates.
- Correct materially stale PR claims when delivery changes them. If documentation
  write-back fails, report remaining work separately from the verified code, merge
  and CI result.
- Query hosted CI at low frequency and for a bounded duration. If the wait times out,
  record the exact pending check or trigger and stop instead of polling indefinitely.
- Before merge, bind the exact base, reviewed HEAD, current PR head, required approvals,
  unresolved review or platform blockers, mergeability, and successful hosted checks.
  The reviewed HEAD, current PR head, and check SHA must identify the same commit. Any
  commit or diff added after review requires targeted re-review before merge.
- After a squash merge, verify that the reviewed head tree equals the merge commit tree.
- Cleanup uses existing explicit authorization for its task-owned targets and resource
  classes. Do not ask again per object within that scope; a new resource class or
  expanded deletion scope goes back to the designated approval owner.
- Remove only task-owned, clean, inactive resources with no open PR or running task,
  after proving that all intended unique changes are retained by merged history, a tag,
  or another explicit authority. Preserve unclear or unrelated resources and confirm
  other worktrees remain unchanged.
- Before and after cleanup, record the final worktree inventory, unique commits, PR state,
  and which task resources were retained or cleaned up.
- Repository or bootstrap setup is complete only after the applicable GitHub-hosted merge policy, security settings, and `main` ruleset are configured and verified by a live API, CLI, or connector re-query.
- Required check names must come from successful hosted runs; never infer them from workflow files or memory.
- Do not push, create or merge a PR, tag, release, publish, or deploy without explicit
  authorization, including a valid user delegation. Tool-required user confirmation
  remains binding.
- Do not start a feature that depends on an unmerged prerequisite unless the dependency and stacking strategy are explicit.

## Issues

Use GitHub Issues for deferred work, work spanning multiple PRs, ongoing investigation, or public collaboration. Handle work within the current approved scope directly; do not use an Issue as a routine execution transcript.

## Security and privacy

- Never commit secrets, tokens, cookies, private keys, real student records, or sensitive local configuration.
- Keep `.env` files untracked and provide safe examples only.
- Treat uploads, URLs, filenames, retrieved content, model output, and tool output as untrusted input.
- Reject path traversal and arbitrary filesystem access; allow only declared roots and manifest-owned paths.
- Do not expose internal stack traces or credentials to browser responses.
- Logs and proof artifacts must redact sensitive fields and remain reproducible without private data.

## Brand and public claims

Night Voyager is an original product name. Do not include copyrighted song lyrics, audio, cover art, animation imagery, franchise logos, or language implying affiliation with an existing work.

Public statements must match repository evidence. Do not claim production deployment, real users, enterprise adoption, accuracy gains, time savings, or business outcomes without reproducible proof. Prefer precise statements such as `local synthetic pilot`, `deterministic fixture`, or `optional adapter` when those are the true boundaries.

## Definition of done

Before declaring a task complete:

1. Confirm the requested scope and non-scope.
2. Run the checks proportional to the change and record actual results.
3. Update affected documentation and evidence.
4. Inspect the final diff for unrelated changes, generated noise, secrets, and private paths.
5. Report the branch and pull request, explicitly stating when no pull request exists.
6. Report the checks actually run, documentation impact, remaining risks, and deferred work.

Optimize for a strong, understandable product and credible engineering evidence. Process exists to protect quality, not to prevent useful work.
