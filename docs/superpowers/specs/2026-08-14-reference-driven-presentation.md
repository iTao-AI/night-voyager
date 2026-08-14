# Night Voyager Reference-Driven Presentation Spec

Status: `LOCAL CANDIDATE / IN REVIEW`
Implementation: `IMPLEMENTED LOCALLY`
Publication: `NOT PUSHED / NOT MERGED / NOT RELEASED / NOT DEPLOYED`
Target repository baseline: `main@e28efdb53d72c8b42c9636f3440dd41ebcb426e0`

This document specifies one presentation-only replacement of the current Night
Voyager public site and advisor-workspace composition. It preserves all existing
domain, API, database, task, session, recovery, and human-authority behavior.

## 1. Outcome

Night Voyager must read as one mature product across `/`,
`/demo/collaboration`, `/demo`, and `/demo/plan`:

- one midnight product environment;
- one dominant mineral/porcelain working surface;
- one five-stage advisor workflow;
- one current business object;
- one clearly responsible human and at most one filled primary action;
- engineering proof after, not before, the business story.

The public site explains what the product does. The three demo routes prove the
same product grammar with real deterministic state and existing actions. The
same-Case journey ends at the persisted receipt and timeline in `/demo`.
`/demo/plan` remains an explicitly separate synthetic execution scenario.

## 2. Locked decisions

The following are already decided and must not be reopened during implementation:

1. Brand: the first-level brand is `Night Voyager`; no Chinese substitute name,
   logo redesign, symbol, third-party font, asset, or visual direction is added.
2. Audience: study-abroad advisors are the primary operator; students and parents
   remain participants at their existing authority boundaries.
3. Visual direction: the approved reference-driven composition and bounded
   depth/material polish are the implementation target. No additional glass,
   glow, effects, cards, metrics, photos, maps, flags, or fake people are added.
4. Product boundary: AI organizes and analyzes; the advisor retains consequential
   professional judgment; the client confirms personal choices and trade-offs.
5. Behavior: existing controllers, reducers, BFF handlers, API contracts, storage
   envelopes, sessions, SSE, idempotency, database state, fixtures, and recovery
   semantics remain unchanged.
6. Technical terms are available only in a closed technical disclosure or in code
   and tests. They are not first-level product language.

## 3. Goals

- Make the first viewport identify a study-abroad advisor product without relying
  on technical terminology or decorative imagery.
- Make the public site and advisor workspace feel like one product world.
- Preserve a truthful, readable path from consultation to confirmed information,
  plan comparison, advisor review, client confirmation, execution follow-up, and
  reassessment.
- Preserve all existing normal, waiting, blocked, recoverable, completed, and
  persisted-result states.
- Reflow intentionally at desktop, tablet, mobile, 200% equivalent zoom, reduced
  motion, and no-blur fallback.
- Keep the entire change deterministic, provider-free, synthetic, public-neutral,
  and dependency-neutral.

## 4. Non-goals

- No backend, API, BFF contract, domain model, schema, migration, database, RLS,
  worker, task lifecycle, session, SSE, idempotency, fixture, or reducer change.
- No DRA or MKE producer/consumer contract change.
- No provider call, live research, analytics, CMS, authentication expansion, real
  customer data, real institution data, admissions outcome, ROI, adoption,
  productivity, production, or deployment claim.
- No new dependency, package, lockfile change, framework migration, font binary,
  image library, icon library, or animation library.
- No deployment, tag, GitHub Release, package publication, repository setting, or
  global Docker/host configuration change.
- No copied Apple, Attio, or other third-party asset, code, font, logo, or exact
  layout.
- No personal website, resume, or private career-material change.
- No alternate visual candidate and no visual shotgun.

## 5. Truth and projection boundary

### 5.1 Public root projection

The root remains a static, read-only React projection. It performs no product-side
request, cookie operation, session bootstrap, storage write, task operation, SSE
subscription, or mutation.

The approved root story uses the existing connected collaboration fixture rather
than the older M3A root-only budget projection:

| Visible fact | Required value |
| --- | --- |
| confirmed planning budget | `¥300,000–400,000` |
| intended field | `计算机方向` |
| underlying field value | `computing` |
| fact version | `1` |
| record revision | `2` |
| Australia | `在预算条件下推荐` |
| Japan | `有条件备选` |
| Malaysia | `暂不可选` |
| route status | `等待顾问审核` |
| next action | `核对路线与依据` |

This is a presentation projection of facts already used by the connected synthetic
journey. It does not rewrite the underlying collaboration or planning fixture.
The previous public-root `¥340,000–400,000` projection is superseded only on the
presentation surface.

### 5.2 Persisted result

The persisted outcome must keep these distinct values:

| Visible fact | Required value |
| --- | --- |
| accepted route | `澳大利亚` |
| accepted budget | `¥305,500–400,000` |
| accepted trade-off | `预算弹性` |
| decision source | `客户直接确认` |
| intake | `2027-02` |
| timeline | `文件准备 2026-09-01 学生` |
| timeline | `提交申请 2026-10-15 学生` |
| timeline | `签证准备 2026-12-15 学生` |
| timeline | `抵达准备 2027-01-20 家长` |

The confirmed planning budget and accepted budget are separate timepoints and must
never be merged.

### 5.3 Server-owned content

Server-owned messages, advisor reasons, evidence limitations, route results, and
identifiers are never rewritten as new facts. In particular, the raw message remains
exactly:

```text
Our confirmed program budget is 300,000 to 400,000 CNY.
```

## 6. Copy contract

Chinese is the deterministic default and the visual acceptance language. English
remains explicitly selectable and must preserve identical semantics, state, action
availability, and authority.

### 6.1 Locked Chinese public copy

Brand positioning:

```text
为留学顾问打造的 AI 协作平台
```

Hero:

```text
让复杂的留学规划，
清晰地向前。
```

Hero explanation:

```text
Night Voyager 帮助顾问把散落在对话里的预算、目标、时间和现实条件整理清楚，再据此比较不同路线、说明推荐理由，并推进下一步。AI 协助整理与分析，关键判断仍由顾问完成。
```

Product reveal:

```text
在一处，看清客户现状、路线差异和下一步。
客户信息、路线比较、判断依据和待办事项彼此衔接。顾问可以随时看清当前进度，以及接下来需要处理什么。
```

Workflow chapters:

```text
重要信息，先确认，再进入方案。
预算、目标、专业方向和时间要求先被整理清楚。只有顾问确认的内容，才会用于后续比较。

不只给出推荐，也把理由说清楚。
不同路线的适用条件、所需预算、准备要求和主要风险并列呈现。顾问可以据此保留、调整或放弃某条路线。

方案经过审核，再交给客户确认。
顾问确认后的路线会整理成清楚的方案和后续安排。客户看到的是经过判断、可以理解也可以确认的结论。

暂停当前流程，从需要重新判断的地方继续。
预算、材料或时间发生变化时，已有进度保留不变，需要重新判断的部分回到顾问手中。
```

Trust and recall:

```text
每一次确认，都能回到当时的情况与依据。
- 哪些信息已经确认，哪些仍待补充
- 为什么推荐、保留或放弃某条路线
- 客户确认了什么，下一步由谁负责
```

Closing:

```text
把复杂信息理清，把关键判断留给顾问。
从第一次咨询到后续执行，重要信息、方案判断和行动安排始终彼此衔接。
```

Non-claim boundary, rendered once on the public page:

```text
产品演示使用合成数据，不包含真实学生资料、录取结果或生产部署信息。
```

### 6.2 Faithful English presentation copy

The English locale is a translation of the locked Chinese contract, not a second
copy direction:

| Purpose | Exact English copy |
| --- | --- |
| positioning | `An AI collaboration platform built for study-abroad advisors` |
| hero | `Move complex study-abroad planning forward with clarity.` |
| explanation | `Night Voyager helps advisors organize the budgets, goals, timelines, and practical constraints scattered across conversations, then compare routes, explain recommendations, and move the next step forward. AI assists with organization and analysis; the advisor retains every consequential judgment.` |
| reveal title | `See the client's current position, route differences, and next step in one place.` |
| reveal body | `Client information, plan comparisons, decision evidence, and next actions stay connected. Advisors can see the current progress and what needs attention next.` |
| chapter 1 | `Confirm important information before it enters the proposal.` |
| chapter 2 | `Explain not only the recommendation, but why.` |
| chapter 3 | `Review the proposal before asking the client to confirm.` |
| chapter 4 | `Pause the current flow and resume from the point that needs new judgment.` |
| trust | `Every confirmation can be traced back to the situation and evidence available at the time.` |
| closing | `Bring complex information into focus and keep consequential judgment with the advisor.` |
| boundary | `The product demo uses synthetic data and contains no real student records, admissions outcomes, or production deployment information.` |

Supporting English body copy must remain a direct semantic translation of the
approved Chinese paragraphs and introduce no additional claim.

### 6.3 First-level vocabulary

| Concept | Chinese | English |
| --- | --- | --- |
| confirmed information | `已确认信息` | `Confirmed information` |
| comparison | `方案比较` | `Plan comparison` |
| advisor gate | `等待顾问审核` | `Awaiting advisor review` |
| client choice | `客户确认` | `Client confirmation` |
| execution | `执行跟进` | `Execution follow-up` |
| reassessment | `重新评估` | `Reassessment` |
| record version | `档案版本` | `Record version` |
| fact version | `事实版本` | `Fact version` |
| persisted receipt | `决策回执` | `Decision receipt` |
| persisted timeline | `行动时间线` | `Action timeline` |

The following are excluded from first-level public/product text and may appear only
inside a closed technical disclosure, GitHub documentation, resume, or interview
material: `受治理`, `服务器授权`, `持久化`, `不可变`, `Evidence`, `Fact version`,
`Case revision`, and `受阻恢复`.

## 7. Public-site information architecture

The public route has this fixed order:

```text
Hero
  -> coded product reveal
  -> confirmed-information chapter
  -> plan-comparison chapter
  -> client-confirmation / persisted-outcome chapter
  -> reassessment trust chapter
  -> recall and engineering disclosure
  -> final CTA and boundary/footer
```

### 7.1 Hero

- One H1 with authored Chinese line spans.
- One explanation paragraph.
- Primary action `查看顾问工作流` scrolls to `#product`.
- Secondary action `GitHub ↗` links to the existing public repository.
- One dominant coded route-analysis product subject; no card grid or raster mockup.

### 7.2 Product reveal and workflow

- The product reveal uses the current route-analysis state and one advisor action
  locus.
- Desktop uses one sticky product frame for confirmed information, plan comparison,
  and persisted outcome. `IntersectionObserver` changes presentation-only scene
  state; it performs no request or business mutation.
- At `≤860px` and under `prefers-reduced-motion: reduce`, all chapters render in
  semantic document order without sticky interpolation.
- The fourth chapter is a separate blocked/reassessment trust proof and never
  implies that `/demo/plan` continues the current Case.

### 7.3 Trust and engineering

- Trust bullets precede engineering details.
- Technical proof is one native `details` element, closed by default.
- The exact non-claim boundary is rendered once outside the dominant product
  subject and not duplicated in the footer.

### 7.4 CTA map

| Surface | Label | Target |
| --- | --- | --- |
| Hero | `查看顾问工作流` | `#product` |
| Hero | `GitHub ↗` | public GitHub repository |
| Product reveal | `核对路线与依据` | `/demo` |
| Final primary | `查看完整咨询流程` | `/demo/collaboration` |
| Final secondary | `查看方案研判` | `/demo` |
| Persisted outcome | `查看正常执行场景` | `/demo/plan` with visible separate-scenario boundary |

No CTA creates a new route or hidden mutation.

## 8. Shared product-frame contract

The root projection and all demo routes reuse one pure presentational product frame:

```text
L0 midnight environment
└── L1 product frame
    ├── top band: current record | stage | status | flow boundary
    ├── stage rail: 01..05
    ├── L2 context plane
    ├── L3 current business object
    ├── L4 human authority and one primary action
    └── L5 closed technical disclosure
```

The frame receives already-authorized display data as props. It does not fetch,
mutate, read storage, infer roles, derive domain state, or own navigation authority.

Desktop uses `2 / 7 / 3` columns for stage/context, current work, and human action.
Tablet uses a `2 × 2` top band, horizontal five-stage rail, full-width work, then
the action layer. Mobile order is:

1. stage and current status;
2. current business object;
3. its evidence or persisted record;
4. responsible human and one next action;
5. lower-priority alternatives/history/timeline;
6. closed technical disclosure.

## 9. Route and state mapping

### 9.1 `/demo/collaboration`

The existing controller remains the only state authority.

| Existing UI state | Primary plane | Human/action plane |
| --- | --- | --- |
| `bootstrapping_parent` | consultation context; no invented values | start the existing walkthrough |
| `thread_ready` | source message or truthful empty state | record message or submit existing proposal |
| `message_submitting` | retained source context | disabled in-progress action |
| `proposal_pending` | proposed information and source | move to existing advisor review |
| `switching_to_advisor` | retained candidate | role handoff status; no guessed authority |
| `advisor_reviewing` | proposed budget, source, record version | advisor confirmation only when current |
| `confirmation_submitting` | retained candidate | disabled publish action |
| `replan_required` | confirmed budget, fact version 1, record version 2 | validated continuation to `/demo` |
| `handoff_validating` | confirmed information retained | one disabled validation action |
| `recoverable_error` | last safe display state | exact existing retry/revalidation action |

The raw message remains visible as source evidence and never becomes the confirmed
fact until the existing advisor action succeeds.

### 9.2 `/demo`

| Existing phase | Primary plane | Human/action plane |
| --- | --- | --- |
| bootstrap/task states | current record and truthful loading/progress | existing task action or waiting state |
| review states | Australia dominant; Japan and Malaysia reduced; evidence and gaps visible | approve or request revision exactly as authorized |
| revision states | changed fact and old/new comparison | existing confirm/create/review action |
| `revision_blocked` | comparison and retained predecessor context | safe exit; no approval or client action |
| `family_review` | server-provided client proposal | existing client confirmation gate |
| `plan_ready` | decision receipt and action timeline | link to explicitly separate execution scenario |
| `terminal_task_failure` | retained safe context and bounded failure | existing safe navigation/recovery only |
| `recoverable_error` | retained ledger/prior state | exact reconnect action |

The semantic comparison table remains available for assistive technology. Desktop
visual emphasis uses one dominant Australia route and two readable alternatives;
mobile uses records, not a compressed six-column table.

### 9.3 `/demo/plan`

| Existing state | Primary plane | Human/action plane |
| --- | --- | --- |
| `loading` | stable frame; name the object being read | no invented action |
| `ready_to_start` | approved plan context | assigned family role starts; advisor cannot |
| `checkpoint_active` | current checkpoint and next actor | accountable role attests |
| `awaiting_advisor` | retained checkpoint and accepted update | assigned advisor verifies or requests update |
| `mutation_in_flight` | last safe state | action disabled |
| `recoverable_error` | last safe state retained | exact authority revalidation |
| `session_changed` | no inferred business state | reconnect through server authority |
| `execution_completed` | verified completion record | no further mutation |
| `reassessment_required` | progress retained; execution stopped | read-only reassessment handoff; no successor |

`happy` and `blocked` scenario parsing, principals, and controller logic are
unchanged. First-level copy says `独立演示场景，不沿用当前客户档案。`

## 10. Material, depth, and motion

### 10.1 Tokens

| Token | Value | Meaning |
| --- | --- | --- |
| environment | `#061117` | midnight page environment |
| product dark | `#0a1c24` / `#102832` | context and status |
| action | `#2b7486` | available governed action |
| current signal | `#75c3d1` | accepted/current structure |
| current soft | `#dcebed` | evidence/context surface |
| intervention | `#ce765f` | human review or exact stop |
| intervention soft | `#f2dfd9` | safe-stop/reassessment surface |
| work surface | `#fcfdfc` | current business object |
| context surface | `#e5eceb` | stage/context plane |
| primary ink | `#102027` | primary text |
| secondary ink | `#52666e` | secondary text |

Cyan never means AI magic. Coral marks a human review, blocked stop, or required
intervention and is always accompanied by text.

### 10.2 Depth budget

- Solid colors, rims, and shadows establish hierarchy first.
- Product frame: one 1px rim, one 18px contact shadow, one 58px ambient shadow.
- Current work has the clearest solid surface and strongest inner rim.
- Dense route data, evidence, receipts, timelines, and full workspaces never use
  backdrop blur.
- At `≥901px`, at most the sticky header (`14px`) and advisor/action rail (`10px`)
  may use blur: maximum two visible surfaces.
- At `561–900px`, only the sticky header may use blur: maximum one surface.
- At `≤560px`, blur and microtexture are disabled: zero surfaces.
- Every blurred surface defines a readable solid fallback before `@supports`.
- A forced no-blur browser audit must preserve dimensions, hierarchy, focus, and
  contrast without implementing prototype query chrome.

### 10.3 Motion

- Hero copy enters with opacity and `translateY(14px)` over `340ms`.
- Hero product enters with opacity, `translateY(34px)`, and `scale(.99)` over
  `520ms`.
- Sticky scene changes use only opacity and transforms no larger than `16px`.
- No filter, blur, shadow, gradient, texture, geometry, or layout animation.
- `prefers-reduced-motion: reduce` renders the complete end state immediately with
  no transform, sticky interpolation, or smooth scroll.

## 11. Typography and accessibility

- Use only system font fallbacks. No font asset or external service.
- Wordmark remains plain text, `20px`, with restrained negative letter spacing.
- Chinese display: `42–68px` marketing and `27–31px` workspace.
- Product labels are never smaller than `12px`.
- Authored line spans exist only in the Hero; no isolated Chinese-character line.
- Exactly one H1 per route and valid heading order.
- Semantic landmarks, lists, tables, forms, buttons, native `details`, status, and
  live-region behavior remain intact.
- Interactive targets are at least `44 × 44px`; primary mobile actions are at
  least `48px` high.
- Focus is visible at all widths and 200% equivalent reflow, never clipped.
- User-initiated accepted transitions return focus to the current-work heading.
  Background status changes use the existing live region without stealing focus.
- Normal text contrast is at least `4.5:1`; large text and focus at least `3:1`.
- No horizontal page overflow or two-dimensional primary-work scrolling at
  `1440`, `1280`, `1024`, `768`, `390`, `320`, or 200% equivalent reflow.

## 12. Failure behavior

Presentation changes must not create a second error model:

- unknown state mappings fail closed and show no raw internal state;
- absent data renders an explicit empty state and no replacement fact;
- transport/session failures retain the last safe content when the existing
  controller provides it;
- disabled actions explain the existing authority requirement;
- lost acknowledgement, stale authority, role rotation, conflict, and recovery
  continue through existing controllers and tests;
- layout, motion, or blur support failure falls back to the complete solid,
  single-column semantic document.

## 13. Acceptance criteria

### Product and copy

- The first viewport uses the locked positioning, Hero, and explanation copy.
- The public site uses the fixed chapter order and all four approved workflow
  paragraphs.
- First-level labels use the approved vocabulary and contain none of the excluded
  technical terms.
- The exact synthetic-data boundary appears once on the public site.
- English is a faithful translation and changes no state or action.

### Truth

- Root current-customer projection uses `¥300,000–400,000`, `计算机方向`, fact
  version 1, record version 2, and the three exact route outcomes.
- Persisted outcome keeps `¥305,500–400,000`, `预算弹性`, `客户直接确认`, and all
  four timeline dates/roles.
- The raw server message remains byte-for-byte unchanged.
- `/demo/collaboration -> /demo` is the only same-Case continuation claim.
- `/demo/plan` visibly states that it does not reuse the current client record.

### Behavior

- Root remains product-side-effect-free.
- Existing request, mutation, reducer, session, SSE, idempotency, recovery, and
  database behavior remains unchanged.
- Every existing route state retains its authorized action or safe no-action state.
- No backend/API/domain/schema/database/reducer/fixture/dependency diff exists.

### Responsive, accessibility, and visual

- Desktop matches the approved composition and `2 / 7 / 3` hierarchy.
- Tablet and mobile use authored reflow, not desktop compression.
- Reduced motion and forced no-blur render complete equivalent information.
- Blur surface counts, contrast, target size, focus, heading, overflow, long-copy,
  and console/hydration gates pass.
- Final real-browser screenshots cover root desktop/mobile, the three sticky
  states, collaboration handoff, advisor review, persisted result, execution
  normal/blocked/recovery/completed, and representative tablet/mobile frames.

### Delivery

- Frontend lint, typecheck, unit tests, build, provider-free backend/architecture
  regression, task-owned Compose proof, Playwright audit, screenshot inspection,
  and one coded design review pass.
- The independent review authority performs a full branch-diff review; execution repairs only
  verified same-scope findings, and authority performs targeted re-review.
- Public scan finds no private path, task identity, credential, real personal data,
  unsupported claim, copied third-party asset, or prototype QA chrome.

## 14. Stop conditions

Stop and return to the authority only if implementation would require:

- a backend/API/domain/schema/database/reducer/fixture/dependency change;
- a change to product direction, audience, scope, route authority, truth boundary,
  approved copy thesis, or visual direction;
- invented data or a screenshot that cannot be produced from coded deterministic
  state;
- a provider, real customer data, deployment, tag, release, account/repository
  setting, global Docker/host change, or broad cleanup;
- an unresolved permission boundary with no safe in-scope recovery.

Ordinary test repair, responsive correction, exact copy-key wiring, no-blur/reduced
motion correction, same-scope review findings, CI repair, PR-body reconciliation,
and task-owned cleanup do not reopen product decisions once the implementation
mandate is approved.
