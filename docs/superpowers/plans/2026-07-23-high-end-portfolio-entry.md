# Night Voyager High-End Portfolio Entry Implementation Plan

**Implementation status:** Complete, merged as PR #60, and released in v0.1.3.

> **Post-implementation correction (current runtime):** The high-end entry was
> merged in PR #60. The homepage now uses the rounded presentation ranges
> `30–40 万元` and `CNY 300,000–400,000`; detailed governed cost and Evidence
> retain the exact `305,500–400,000 CNY` range. The task checklist and historical
> approved examples below preserve the original implementation plan rather than
> retroactively rewriting it as the current runtime contract.

> **For agentic workers:** REQUIRED PRIMARY CONTROLLER: use
> `superpowers:executing-plans`. Follow every frontend, asset, browser, and
> documentation slice with RED -> GREEN. Do not combine this plan with another
> execution controller. Run `design-review` once after the implementation is
> complete and before the branch is handed off for authority review.

**Goal:** Replace the current warm-paper root portfolio entry with the approved
Chinese-first “虚幻夜航” presentation so a non-technical reviewer can understand the
student value, recommended route, trade-offs, and next action in the first viewport,
while preserving the existing governed demo flows and every backend authority
boundary.

**Architecture:** The root route receives a route-specific presentation shell and
three small visual components: a responsive cinematic backdrop, an accessible route
atlas, and a continuous decision journey. The shared `PresentationProvider`,
`LocaleSwitch`, closed copy catalog, and exact locale storage contract remain the
only presentation state. `/demo` and `/demo/collaboration` keep the existing
`PresentationShell` and warm-paper ledger system. The root remains a static,
provider-free portfolio surface with zero API, cookie, session, task, SSE, or
database effects.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, existing project CSS,
Vitest, Testing Library, Playwright/Chromium, checked-in AVIF/WebP assets derived
from the approved source image, and the current locked npm tree. No new runtime,
frontend, font, icon, animation, image, or component dependency.

## Status

- Product direction: approved and visually frozen.
- Approved variant: `A3`, derived from source direction `A`.
- Design artifact SHA-256:
  `c426139a80cce7260bfb3e2160dd82509cd9b8ef454c1d6f87dfda1ad3b6a3ae`.
- Approved source image:
  - dimensions: `1672 × 941`;
  - bytes: `1,662,495`;
  - SHA-256:
    `4fe73754e5180e725bfc7d734fc9a9039030da5ebef41f31aa1cf2f1ccff55fc`.
- Design review: `A-`; AI-slop review: `A`.
- Implementation: merged as PR #60 and released in v0.1.3 with the later
  route-presentation correction.

The source image is supplied to the implementation owner as an approved input.
Repository artifacts may record only the approved file identity, dimensions,
neutral provenance, and checked-in destination; machine-specific source locations
must not enter source, tests, docs, commits, or PR text.

## Exact Starting Point

Before implementation, re-query the repository rather than trusting this planning
snapshot.

- Expected repository: `iTao-AI/night-voyager`.
- Planning snapshot:
  `main == origin/main == 6c0ac0047eb99305b45e4c99a1e0a22a250bf87d`.
- Expected current capability:
  - PR 1 explicit planning-start authority is merged;
  - PR 2 governed fact-to-plan walkthrough is merged;
  - PR 3 Chinese-first presentation is merged;
  - v0.1.2 remains the latest published tag;
  - post-v0.1.2 work remains unreleased.
- Begin only from clean, exact current `main`.
- If `main` moved, record the new base and inspect all root presentation drift before
  continuing. Do not mechanically replay against an unknown tree.

## Global Constraints

- Scope is the public root `/` presentation and its direct tests, screenshots, and
  current documentation.
- Do not change:
  - migrations, PostgreSQL functions, tables, grants, RLS, roles, or seeds;
  - FastAPI, BFF routes, HTTP schemas, problem codes, cookies, Origin/CSRF, or
    idempotency;
  - task, worker, Skill, SSE, recovery, DRA, MKE, or provider behavior;
  - dependency manifests, lockfiles, CI, Compose services, package version, tag,
    release, or deployment configuration;
  - Dockerfiles, except for the exact standalone public-assets copy authorized
    below.
- Narrow Dockerfile amendment:
  - Next.js standalone output does not copy `public` by default;
  - `web/Dockerfile` may add exactly
    `COPY --from=builder --chown=nextjs:nodejs /app/public ./public`;
  - it must appear after the existing `.next/standalone` and `.next/static` copies
    and before `USER nextjs`;
  - architecture proof must lock the exact source, destination, ownership, and
    pre-`USER` position;
  - real Chromium must prove the selected AVIF/WebP has `naturalWidth > 0`;
  - no other Dockerfile, Compose, build-context, user, permission, image, or
    deployment change is authorized by this exception.
- `/demo` and `/demo/collaboration` retain the current warm-paper/ledger visual
  system. Do not globally restyle `PresentationShell`, `.demo-shell`, ledger,
  collaboration, family record, task, or inspector surfaces.
- `/` remains a static portfolio route:
  - no `fetch`;
  - no BFF/API request;
  - no session bootstrap, mint, revoke, cookie, or CSRF action;
  - no `sessionStorage` journey state;
  - no task, EventSource, polling, retry, or mutation.
- Supported locales remain exactly `zh-CN` and `en`.
  - SSR/default/fail-closed locale is `zh-CN`;
  - explicit English switch is exact `en`;
  - key remains `night-voyager:presentation-locale:v1`;
  - switching locale changes presentation only.
- The public headline is exact and punctuation-free:

  ```text
  你的留学路线
  应该从你出发
  ```

- The Chinese subtitle is exact:

  ```text
  不只告诉你去哪留学，更要说清为什么适合你。看懂不同路线的理由与取舍，再把选择变成一份可以执行的计划。
  ```

- The English surface expresses the same hierarchy and evidence; it is not a second
  product narrative.
- Route facts remain the checked-in synthetic example:
  - intended field: data science;
  - budget: `30.55–40 万元` / `CNY 305,500–400,000`;
  - Australia: recommended;
  - Japan: reserve;
  - Malaysia: not recommended at present.
- Do not claim real student use, live institutional coverage, admission outcomes,
  production deployment, business impact, SLA, or provider execution.
- The route visualization must show the reason and trade-off, not only a country
  ranking.
- The first viewport must expose:
  1. product thesis;
  2. synthetic student starting conditions;
  3. recommended/reserve/currently-not-recommended route structure;
  4. one primary route into the complete governed demo.
- The second section must preserve the approved continuous journey:
  - 理解你的条件;
  - 看懂理由与取舍;
  - 形成可执行计划.
- The page may use restrained CSS-only motion:
  - slow background drift;
  - subtle star twinkle;
  - route drawing/reveal.
- Do not add pointer-following parallax, canvas, WebGL, video, animation libraries,
  randomly generated stars, requestAnimationFrame loops, scroll-jacking, autoplay
  audio, or state that depends on animation completion.
- `prefers-reduced-motion: reduce` must render all content immediately and disable
  decorative animation.
- Preserve:
  - one H1;
  - ordered H2/H3 hierarchy;
  - banner/main/contentinfo landmarks;
  - working skip link;
  - visible keyboard focus;
  - 44 px minimum interactive targets;
  - minimum 16 px body copy;
  - sufficient text contrast;
  - no horizontal overflow at 320, 390, 768, and 1440 px.
- Avoid:
  - purple SaaS gradients;
  - generic three-card marketing grids;
  - floating decorative spheres;
  - icon-circle feature rows;
  - glassmorphism on every surface;
  - cheap particles;
  - oversized empty space that hides route outcomes;
  - family-first wording on the root;
  - raw codes, UUIDs, hashes, JSON, or internal state labels in visible copy.
- Derived AVIF/WebP images are production inputs. The approved PNG is a design source
  only and must not be the sole runtime resource.
- Preserve all immutable v0.1.0, v0.1.1, and v0.1.2 release documents and their
  digests.
- Do not bump the package version or prepare a release in this PR.
- Before Docker/Chromium verification, run `make doctor MODE=dev` and record host
  plus Docker VM capacity. Use the existing task-scoped Compose lifecycle; do not
  prune, alter Docker Desktop settings, or delete retained data without new
  authorization.
- Stop after a clean local branch, full verification, visual review, docs audit, and
  authority-review handoff. Push, PR, merge, release, deploy, provider execution, and
  cleanup remain separately authorized.

## Approved Information Architecture

### Root header

```text
Night Voyager
规划思路  路线示例  决策依据
中文 / English
体验完整流程
本地合成演示
```

- `规划思路` / `Approach` -> `#journey`.
- `路线示例` / `Route example` -> `#route-atlas`.
- `决策依据` / `Decision evidence` -> `/demo`.
- Header action -> `/demo/collaboration`.
- Mobile may collapse the three center links, but the brand, locale switch,
  synthetic boundary, and complete-flow action remain discoverable and keyboard
  reachable.

### Hero

```text
01  从你出发的路线

你的留学路线
应该从你出发

不只告诉你去哪留学，更要说清为什么适合你。
看懂不同路线的理由与取舍，再把选择变成一份可以执行的计划。

[查看示例方案] -> /demo/collaboration
[查看路线依据] -> #route-atlas
```

The primary CTA starts the complete governed flow. It must not be a dead marketing
anchor. The secondary CTA keeps the route evidence in the same page.

### Route atlas

The accessible route description is equivalent to:

```text
学生希望学习数据科学，预算 30.55–40 万元。
澳大利亚为推荐路线，日本为备选路线，马来西亚暂不推荐。
```

Desktop:

```text
origin: 数据科学 / 预算 30.55–40 万元
  -> Australia · 推荐
     专业衔接与预算区间更匹配
  -> Japan · 备选
     保留语言与时间准备弹性
  -> Malaysia · 暂不推荐
     当前专业选择不足以支撑优先级
```

Tablet/mobile:

```text
01 澳大利亚  推荐
02 日本      备选
03 马来西亚  暂不推荐
```

The compact summary is a visual alternative to the full desktop SVG. Expose one
canonical screen-reader description rather than duplicate announcements.

### Journey

```text
02 / 从路线比较到下一步

先看清自己
再决定去哪里

同一个专业、同一段预算，会因为你的背景、偏好与承受边界，
长出完全不同的路线。Night Voyager 把比较的理由摊开，
也把下一步排进日程。

01 · 出发点      理解你的条件
02 · 路线比较    看懂理由与取舍
03 · 行动坐标    形成可执行计划
```

Use one continuous visual trajectory, not three disconnected feature cards.

### Boundary and disclosure

Keep the boundary visible:

```text
本地合成演示 · 非生产部署 · 不使用真实学生数据
```

Keep a native `<details>` disclosure after the primary story. It may explain the
provider-free deterministic boundary and link to the focused evidence route, but it
must not dominate the first viewport.

## Component Boundary

The preferred implementation is:

```text
web/app/page.tsx
  PortfolioShell
    PortfolioEntry
      PortfolioBackdrop
      PortfolioRouteAtlas
      PortfolioJourney
```

### `PortfolioShell`

- root-only skip link, header, nav, locale control, synthetic label, main, and footer;
- owns class namespace `.portfolio-night`;
- does not replace or modify the shared `PresentationShell`;
- consumes only `usePresentation()` and `LocaleSwitch`.

### `PortfolioBackdrop`

- semantic decorative `<picture>`;
- AVIF first, WebP fallback;
- fixed intrinsic width/height;
- `alt=""`, `aria-hidden="true"`;
- eager/high-priority loading because it is the LCP visual;
- deterministic checked-in star elements, not random runtime output.

### `PortfolioRouteAtlas`

- uses closed `PORTFOLIO_ROUTE_STOPS`;
- desktop SVG with `<title>` and `<desc>`;
- mobile/tablet summary;
- no client state and no route selection interaction;
- does not fabricate server reads.

### `PortfolioJourney`

- one section and one ordered list;
- three semantic steps;
- native boundary/disclosure;
- no card-grid layout.

## Closed Presentation Data

Create one small project-owned static contract:

```typescript
export const PORTFOLIO_ROUTE_STOPS = [
  {
    id: "australia",
    countryKey: "countryAustralia",
    statusKey: "rootRouteRecommended",
    reasonKey: "rootRouteAustraliaReason",
    emphasis: "primary",
  },
  {
    id: "japan",
    countryKey: "countryJapan",
    statusKey: "rootRouteReserve",
    reasonKey: "rootRouteJapanReason",
    emphasis: "secondary",
  },
  {
    id: "malaysia",
    countryKey: "countryMalaysia",
    statusKey: "rootRouteNotRecommended",
    reasonKey: "rootRouteMalaysiaReason",
    emphasis: "muted",
  },
] as const;
```

Use catalog keys for every visible label. Do not add raw route strings to the
component.

Required new catalog concepts:

```text
rootEyebrow
rootTitleLineOne
rootTitleLineTwo
rootSummary
rootPrimaryAction
rootSecondaryAction
rootNavigationLabel
rootNavApproach
rootNavRoutes
rootNavEvidence
rootHeaderAction
rootOriginLabel
rootOriginField
rootOriginBudget
rootRouteAtlasTitle
rootRouteAtlasDescription
rootRouteSummaryLabel
rootRouteRecommended
rootRouteReserve
rootRouteNotRecommended
rootRouteAustraliaReason
rootRouteJapanReason
rootRouteMalaysiaReason
rootJourneyIndex
rootJourneyTitleLineOne
rootJourneyTitleLineTwo
rootJourneyLead
rootJourneyStepOneIndex
rootJourneyStepOneTitle
rootJourneyStepOneBody
rootJourneyStepTwoIndex
rootJourneyStepTwoTitle
rootJourneyStepTwoBody
rootJourneyStepThreeIndex
rootJourneyStepThreeTitle
rootJourneyStepThreeBody
rootScrollCue
```

Retire or repurpose the old root-only outcome-ledger copy. Do not remove any key
still used by `/demo`, `/demo/collaboration`, tests, or current public docs.

`productPromise`, `documentTitle`, and `documentDescription` must agree with the new
root thesis in both locales.

## Asset Contract

Create:

```text
docs/assets/design/night-voyager-voyage-source.png
web/public/portfolio/night-voyager-voyage-960.avif
web/public/portfolio/night-voyager-voyage-1680.avif
web/public/portfolio/night-voyager-voyage-960.webp
web/public/portfolio/night-voyager-voyage-1680.webp
```

Rules:

- Verify the source SHA-256 before copying.
- Strip metadata while deriving production assets.
- Keep aspect ratio `1672 / 941`.
- The `960` variants target small/tablet displays.
- The `1680` variants target desktop/retina layouts without exceeding the approved
  source dimensions.
- AVIF is preferred; WebP is fallback.
- Do not add a PNG source to `web/public`.
- Do not add a new npm dependency or script solely for one-time conversion.
- The current locked npm tree already resolves `sharp` through Next.js. It may be
  used as a one-time local conversion tool if present after `npm ci`; the committed
  contract is the resulting image identity, dimensions, and browser decoding, not a
  new runtime import.
- If the locked environment cannot perform deterministic conversion, stop and
  report the exact tool gap. Do not download an unreviewed converter.
- Record final production asset bytes and SHA-256 in the implementation handoff and
  architecture test.
- Keep every production variant substantially smaller than the 1,662,495-byte source
  unless visual review proves the limit would materially damage the approved design.

Representative conversion:

```bash
cd web
node --input-type=module <<'NODE'
import sharp from "sharp";

const source = "../docs/assets/design/night-voyager-voyage-source.png";
for (const width of [960, 1680]) {
  const image = sharp(source).resize({
    width,
    withoutEnlargement: true,
    fit: "inside",
  });
  await image.clone().avif({ quality: 66, effort: 6 })
    .toFile(`public/portfolio/night-voyager-voyage-${width}.avif`);
  await image.clone().webp({ quality: 78, effort: 6 })
    .toFile(`public/portfolio/night-voyager-voyage-${width}.webp`);
}
NODE
```

This is an implementation example, not permission to change dependency files.

---

### Task 1: Freeze the root presentation and route data contracts

**Files:**

- Create: `web/lib/presentation/portfolio.ts`
- Modify: `web/lib/presentation/catalog.ts`
- Modify: `web/tests/unit/presentation-catalog.test.ts`
- Create: `web/tests/unit/portfolio-route-contract.test.ts`
- Modify: `web/tests/unit/portfolio-entry.test.tsx`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`

- [ ] **Step 1: Write exact copy and route RED tests**

  Lock:

  - headline lines without punctuation;
  - exact Chinese subtitle;
  - English key parity;
  - exact three-country route order and emphasis;
  - exact CTA paths;
  - absence of the old family-first headline;
  - one H1 and native disclosure;
  - zero `fetch` and zero journey `sessionStorage` access.

  Representative assertions:

  ```typescript
  expect(zhCN.rootTitleLineOne).toBe("你的留学路线");
  expect(zhCN.rootTitleLineTwo).toBe("应该从你出发");
  expect(zhCN.rootSummary).toBe(
    "不只告诉你去哪留学，更要说清为什么适合你。看懂不同路线的理由与取舍，再把选择变成一份可以执行的计划。",
  );
  expect(PORTFOLIO_ROUTE_STOPS.map(({ id }) => id)).toEqual([
    "australia",
    "japan",
    "malaysia",
  ]);
  ```

- [ ] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- \
    presentation-catalog \
    portfolio-route-contract \
    portfolio-entry \
    presentation-accessibility
  ```

  Expected: missing route contract and catalog keys; old headline assertions fail.

- [ ] **Step 3: Implement the closed data and copy surface**

  - Add `PORTFOLIO_ROUTE_STOPS`.
  - Add exact `zh-CN` and `en` keys.
  - Update document metadata copy.
  - Keep catalog parity and the existing 240-character bound.
  - Do not touch domain code maps or formatters.

- [ ] **Step 4: Keep the UI RED narrow**

  Run the same tests. Catalog/route-contract tests should turn green while
  `portfolio-entry` remains red because the UI has not adopted the new contract.
  Confirm failure is limited to expected UI assertions.

- [ ] **Step 5: Commit the green contract slice**

  ```bash
  npm --prefix web run test -- presentation-catalog portfolio-route-contract
  npm --prefix web run lint
  npm --prefix web run typecheck
  git diff --check
  git add \
    web/lib/presentation/portfolio.ts \
    web/lib/presentation/catalog.ts \
    web/tests/unit/presentation-catalog.test.ts \
    web/tests/unit/portfolio-route-contract.test.ts
  git diff --cached --check
  git commit -m "feat: freeze the high-end portfolio contract"
  ```

---

### Task 2: Add the approved responsive visual assets

**Files:**

- Create: `docs/assets/design/night-voyager-voyage-source.png`
- Create: `web/public/portfolio/night-voyager-voyage-960.avif`
- Create: `web/public/portfolio/night-voyager-voyage-1680.avif`
- Create: `web/public/portfolio/night-voyager-voyage-960.webp`
- Create: `web/public/portfolio/night-voyager-voyage-1680.webp`
- Create: `tests/architecture/test_portfolio_presentation_contract.py`

- [ ] **Step 1: Verify the supplied source before repository copy**

  ```bash
  shasum -a 256 "$APPROVED_PORTFOLIO_SKY_SOURCE"
  sips -g pixelWidth -g pixelHeight "$APPROVED_PORTFOLIO_SKY_SOURCE"
  ```

  Expected exact source:

  ```text
  sha256 4fe73754e5180e725bfc7d734fc9a9039030da5ebef41f31aa1cf2f1ccff55fc
  width 1672
  height 941
  ```

  Stop if any value differs.

- [ ] **Step 2: Write asset RED**

  The architecture test must require:

  - source PNG exact SHA and dimensions;
  - four production files;
  - valid AVIF/WebP signatures;
  - positive dimensions and expected aspect ratio;
  - `960` and `1680` width classes;
  - actual file size below source;
  - no source PNG under `web/public`;
  - no dependency or lockfile change.

  Do not hard-code production hashes until the files are generated and inspected.

- [ ] **Step 3: Run RED**

  ```bash
  uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
  ```

  Expected: missing source and production assets.

- [ ] **Step 4: Copy, derive, inspect, and lock assets**

  - Copy the approved source to the exact docs path.
  - Generate all four production variants.
  - Record byte counts and SHA-256.
  - Open the `1680` AVIF/WebP render and compare it with the approved source.
  - Lock observed identities in the architecture test.
  - Confirm no private path or image metadata is present.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
  git diff --check
  git add \
    docs/assets/design/night-voyager-voyage-source.png \
    web/public/portfolio/night-voyager-voyage-960.avif \
    web/public/portfolio/night-voyager-voyage-1680.avif \
    web/public/portfolio/night-voyager-voyage-960.webp \
    web/public/portfolio/night-voyager-voyage-1680.webp \
    tests/architecture/test_portfolio_presentation_contract.py
  git diff --cached --check
  git commit -m "feat: add responsive voyage imagery"
  ```

---

### Task 3: Build a root-only cinematic shell and route atlas

**Files:**

- Create: `web/components/presentation/PortfolioShell.tsx`
- Create: `web/components/presentation/PortfolioBackdrop.tsx`
- Create: `web/components/presentation/PortfolioRouteAtlas.tsx`
- Modify: `web/components/presentation/PortfolioEntry.tsx`
- Modify: `web/app/page.tsx`
- Modify: `web/app/layout.tsx`
- Modify: `web/app/styles.css`
- Modify: `web/tests/unit/portfolio-entry.test.tsx`
- Modify: `web/tests/unit/presentation-shell.test.tsx`
- Create: `web/tests/unit/portfolio-route-atlas.test.tsx`

- [ ] **Step 1: Extend RED for root isolation and semantic routes**

  Assert:

  - `/` uses `PortfolioShell`;
  - shared `PresentationShell` remains used by both demo pages;
  - one banner/main/contentinfo and one H1;
  - exact headline lines;
  - exact navigation and CTA hrefs;
  - route atlas has one canonical accessible description;
  - three routes and reasons are present;
  - decorative backdrop has empty alternative text;
  - `<picture>` lists AVIF before WebP;
  - no API/session/task side effect;
  - current demo shell behavior remains green.

- [ ] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- \
    portfolio-entry \
    portfolio-route-atlas \
    presentation-shell \
    presentation-accessibility \
    design-contract
  ```

  Expected: new components/selectors are absent.

- [ ] **Step 3: Implement `PortfolioShell`**

  Representative structure:

  ```tsx
  export function PortfolioShell({ children }: { children: ReactNode }) {
    const { copy } = usePresentation();
    return (
      <div className="portfolio-night">
        <a className="skip-link portfolio-skip-link" href="#main-content">
          {copy("skipToMain")}
        </a>
        <header className="portfolio-nav">
          <Link className="portfolio-brand" href="/">
            <span className="portfolio-brand-mark" aria-hidden="true" />
            {copy("productName")}
          </Link>
          <nav aria-label={copy("rootNavigationLabel")}>
            <a href="#journey">{copy("rootNavApproach")}</a>
            <a href="#route-atlas">{copy("rootNavRoutes")}</a>
            <Link href="/demo">{copy("rootNavEvidence")}</Link>
          </nav>
          <div className="portfolio-nav-actions">
            <LocaleSwitch />
            <Link href="/demo/collaboration">{copy("rootHeaderAction")}</Link>
          </div>
          <span className="portfolio-synthetic-label">
            {copy("syntheticLabel")}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>{children}</main>
        <footer className="portfolio-footer">{copy("footerBoundary")}</footer>
      </div>
    );
  }
  ```

  Mobile may present a reduced nav, but never hide the locale switch or complete-flow
  action from keyboard and screen-reader users.

- [ ] **Step 4: Implement the deterministic backdrop**

  Use a `<picture>` with explicit sources and a finite checked-in star list:

  ```tsx
  const STARS = [
    { x: "14%", y: "18%", size: "2px", delay: "-1.2s", duration: "5.8s" },
    // bounded, deterministic decorative positions
  ] as const;
  ```

  Decorative stars must be `aria-hidden`. Do not generate positions during render.

- [ ] **Step 5: Implement the route atlas**

  - Translate the approved SVG into JSX.
  - Prefix SVG IDs with `portfolio-` to avoid collisions.
  - Put localized `<title>` and `<desc>` inside the SVG.
  - Render the compact summary for tablet/mobile.
  - Keep one screen-reader description; mark the duplicate visual summary
    appropriately.
  - Use route data from `PORTFOLIO_ROUTE_STOPS`.

- [ ] **Step 6: Rewrite the hero without changing demos**

  - `PortfolioEntry` owns hero copy, CTAs, and route atlas.
  - `page.tsx` uses `PortfolioShell`, not `PresentationShell`.
  - `layout.tsx` static metadata matches the default Chinese catalog.
  - Keep `PresentationProvider` in the root layout.
  - Do not edit demo components to fit the new visual system.

- [ ] **Step 7: Add root-scoped CSS**

  All new selectors start with `.portfolio-` or are descendants of
  `.portfolio-night`.

  Use:

  - deep midnight/navy background;
  - ivory body text;
  - champagne-gold emphasis;
  - Chinese serif headline;
  - subtle grain/nebula/horizon layers;
  - left thesis/right atlas desktop composition;
  - local `:has(.portfolio-night)` backdrop only if required to prevent warm
    overscroll; it must not match demo routes.

  Do not overwrite existing demo tokens or reuse generic `.primary-action` selectors
  for the new buttons.

- [ ] **Step 8: Run GREEN and compatibility tests**

  ```bash
  npm --prefix web run test -- \
    portfolio-entry \
    portfolio-route-atlas \
    presentation-shell \
    presentation-accessibility \
    design-contract
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  ```

- [ ] **Step 9: Commit**

  ```bash
  git add \
    web/components/presentation/PortfolioShell.tsx \
    web/components/presentation/PortfolioBackdrop.tsx \
    web/components/presentation/PortfolioRouteAtlas.tsx \
    web/components/presentation/PortfolioEntry.tsx \
    web/app/page.tsx \
    web/app/layout.tsx \
    web/app/styles.css \
    web/tests/unit/portfolio-entry.test.tsx \
    web/tests/unit/presentation-shell.test.tsx \
    web/tests/unit/portfolio-route-atlas.test.tsx
  git diff --cached --check
  git commit -m "feat: add the cinematic portfolio route"
  ```

---

### Task 4: Implement the continuous journey and responsive accessibility

**Files:**

- Create: `web/components/presentation/PortfolioJourney.tsx`
- Modify: `web/components/presentation/PortfolioEntry.tsx`
- Modify: `web/app/styles.css`
- Create: `web/tests/unit/portfolio-journey.test.tsx`
- Modify: `web/tests/unit/presentation-accessibility.test.tsx`
- Modify: `tests/architecture/test_portfolio_presentation_contract.py`

- [ ] **Step 1: Write journey, responsive, and motion RED**

  Tests must require:

  - exact H2 and three ordered H3s in both locales;
  - an ordered list, not generic independent cards;
  - route/journey anchors;
  - visible boundary and native disclosure;
  - `.portfolio-night` root namespace;
  - explicit `1023`, `767`, and small-mobile behavior;
  - a `320`-safe minimum layout;
  - `prefers-reduced-motion`;
  - all decorative animation disabled/reduced under that query;
  - no canvas/WebGL/video/runtime random/pointer tracking;
  - no dependency/lockfile changes.

- [ ] **Step 2: Run RED**

  ```bash
  npm --prefix web run test -- \
    portfolio-journey \
    presentation-accessibility
  uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
  ```

- [ ] **Step 3: Implement `PortfolioJourney`**

  Representative semantic structure:

  ```tsx
  <section id="journey" className="portfolio-journey"
    aria-labelledby="portfolio-journey-title">
    <header>
      <p>{copy("rootJourneyIndex")}</p>
      <h2 id="portfolio-journey-title">
        {copy("rootJourneyTitleLineOne")}
        <span>{copy("rootJourneyTitleLineTwo")}</span>
      </h2>
      <p>{copy("rootJourneyLead")}</p>
    </header>
    <ol className="portfolio-journey-track">
      {steps.map(...)}
    </ol>
    <details className="portfolio-disclosure">
      <summary>{copy("rootScopeTitle")}</summary>
      <p>{copy("rootScopeBody")}</p>
    </details>
  </section>
  ```

- [ ] **Step 4: Implement responsive behavior**

  - `>=1024`: full route atlas and asymmetric hero.
  - `768–1023`: compact route summary, readable hero, no clipped country outcomes.
  - `<768`: one column, compact nav, full-width primary CTA, journey line becomes
    vertical.
  - `320–389`: preserve headline, summary, all three route outcomes, locale, CTA,
    and no horizontal overflow.
  - Keep mobile content in semantic DOM order.

- [ ] **Step 5: Implement restrained motion and reduced-motion fallback**

  - Keyframes only for decorative drift, twinkle, and path reveal.
  - No content starts as permanently invisible.
  - Under reduced motion:

    ```css
    @media (prefers-reduced-motion: reduce) {
      .portfolio-night *,
      .portfolio-night *::before,
      .portfolio-night *::after {
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .01ms !important;
      }
      .portfolio-route-path {
        stroke-dashoffset: 0;
      }
    }
    ```

- [ ] **Step 6: Run GREEN and commit**

  ```bash
  npm --prefix web run test -- \
    portfolio-entry \
    portfolio-route-atlas \
    portfolio-journey \
    presentation-accessibility \
    presentation-catalog
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run build
  uv run pytest -q tests/architecture/test_portfolio_presentation_contract.py
  git diff --check
  git add \
    web/components/presentation/PortfolioJourney.tsx \
    web/components/presentation/PortfolioEntry.tsx \
    web/app/styles.css \
    web/tests/unit/portfolio-journey.test.tsx \
    web/tests/unit/presentation-accessibility.test.tsx \
    tests/architecture/test_portfolio_presentation_contract.py
  git diff --cached --check
  git commit -m "feat: add the portfolio decision journey"
  ```

---

### Task 5: Prove the real browser surface and refresh public evidence

**Files:**

- Modify: `web/Dockerfile`
- Modify: `web/e2e/bootstrap.spec.ts`
- Modify: `web/e2e/fact-to-plan.spec.ts`
- Modify: `tests/architecture/test_compose_contract.py`
- Modify: `tests/unit/test_release_surface.py`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `scripts/verify_release.py`
- Modify: `docs/assets/night-voyager-portfolio-entry.png`

- [ ] **Step 1: Write browser and screenshot RED**

  Required evidence:

  - default exact `zh-CN`;
  - explicit exact `en`;
  - no root API request;
  - no root session journey;
  - exact CTA links;
  - route description and all three outcomes;
  - 1440, 768, 390, and 320 px;
  - no horizontal overflow;
  - primary action and locale controls at least 44 px;
  - no clipped visible text;
  - keyboard skip-link focus;
  - reduced-motion context still shows all route results;
  - the selected standalone AVIF/WebP completes with `naturalWidth > 0`;
  - a fresh 1440 px Chinese screenshot from the real Compose Chromium lane;
  - screenshot is a PNG, width 1440, height at least 900;
  - screenshot and page contain no raw UUID, JSON, traceback, credential, private
    path, or internal role name.

  Update the required `fact-to-plan` root assertions rather than creating an
  unexecuted screenshot-only test.

- [ ] **Step 2: Run focused RED**

  ```bash
  npm --prefix web run test -- portfolio-entry presentation-accessibility
  uv run pytest -q \
    tests/architecture/test_compose_contract.py \
    tests/unit/test_release_surface.py \
    tests/architecture/test_documentation_governance.py
  ```

  Expected: stale screenshot/copy/evidence assertions fail.

- [ ] **Step 3: Extend real Chromium proof**

  Add the exact approved `web/Dockerfile` public-assets copy before the runtime
  `USER nextjs` boundary. This is required because Next.js standalone output does
  not include `public` automatically. Do not copy the design-source PNG into the
  runtime image and do not change the runtime user or permissions.

  In `fact-to-plan.spec.ts`, before entering the business flow:

  - verify the new root;
  - verify zero mutation and zero EventSource requests;
  - verify no `night-voyager:m5`;
  - run root responsive checks;
  - capture the Chinese screenshot only when the existing screenshot update flag is
    enabled;
  - keep the full zh-CN and English governed fact-to-plan flow unchanged afterward.

  Add reduced-motion coverage with a separate browser context or
  `page.emulateMedia({ reducedMotion: "reduce" })`; do not mutate product code to
  expose a test hook.

  Extend `scripts/verify_release.py` so development/release-tree verification checks
  the root screenshot, approved source identity, four optimized production assets,
  root component inventory, and truthful README discovery. The verifier must inspect
  bounded identities and file signatures; it must not import frontend runtime code
  or depend on a private design-source location.

- [ ] **Step 4: Run local browser proof with formal Docker preflight**

  ```bash
  make doctor MODE=dev
  make compose-proof
  make down
  docker compose ps --all
  ```

  Expected:

  - one top-level `make compose-proof` exit 0;
  - both locale lanes pass;
  - root screenshot is regenerated by the Chinese lane;
  - database verifier remains unchanged;
  - final Compose inventory is empty;
  - retained data is untouched.

- [ ] **Step 5: Inspect the screenshot manually**

  Review the real file at:

  ```text
  docs/assets/night-voyager-portfolio-entry.png
  ```

  Confirm:

  - the first viewport communicates thesis, origin, and routes;
  - text remains legible over the backdrop;
  - the route atlas does not overpower the left copy;
  - Australia/Japan/Malaysia status is visible;
  - no warm-paper root residue;
  - no private/debug content;
  - no browser chrome;
  - no clipping or horizontal overflow.

- [ ] **Step 6: Lock evidence and commit**

  ```bash
  uv run pytest -q \
    tests/architecture/test_compose_contract.py \
    tests/unit/test_release_surface.py \
    tests/architecture/test_documentation_governance.py
  git diff --check
  git add \
    web/Dockerfile \
    web/e2e/bootstrap.spec.ts \
    web/e2e/fact-to-plan.spec.ts \
    tests/architecture/test_compose_contract.py \
    tests/unit/test_release_surface.py \
    tests/architecture/test_documentation_governance.py \
    scripts/verify_release.py \
    docs/assets/night-voyager-portfolio-entry.png
  git diff --cached --check
  git commit -m "test: prove the high-end portfolio entry"
  ```

---

### Task 6: Reconcile public documentation and implementation status

**Files:**

- Modify: `README.md`
- Modify: `README_CN.md`
- Modify: `DESIGN.md`
- Modify: `docs/README.md`
- Modify: `docs/design/demo-storyboard.md`
- Modify: `docs/design/route-map.md`
- Modify:
  `docs/superpowers/plans/2026-07-22-chinese-first-portfolio-presentation.md`
- Create:
  `docs/superpowers/plans/2026-07-23-high-end-portfolio-entry.md`
- Modify: `tests/architecture/test_documentation_governance.py`
- Modify: `tests/unit/test_release_surface.py`

- [ ] **Step 1: Write documentation RED**

  Require current docs to say:

  - root is the high-end Chinese-first route entry;
  - root is static, local synthetic, and provider-free;
  - `/demo/collaboration` is the complete governed walkthrough;
  - `/demo` is the focused advisor-family/evidence route;
  - root uses optimized AVIF/WebP while the source PNG is provenance only;
  - demo routes retain the warm-paper ledger system;
  - PR 3 presentation work is merged, not “local for authority review”;
  - v0.1.2 is still the latest published release;
  - current post-v0.1.2 work is unreleased;
  - immutable historical release files remain unchanged.

- [ ] **Step 2: Run RED**

  ```bash
  uv run pytest -q \
    tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  ```

- [ ] **Step 3: Update public docs**

  `DESIGN.md` must explicitly describe two visual layers:

  1. root `/`: virtual night voyage, deep navy/ivory/champagne, route atlas;
  2. governed demo routes: existing warm-paper ledger/family decision documents.

  Do not rewrite tagged release notes or imply the new root shipped in v0.1.2.

  Replace stale “PR 3 implemented locally for authority review” statements with the
  merged truth. The new plan starts as approved and, after implementation, records
  local completion for authority review.

- [ ] **Step 4: Run one documentation release audit**

  Use `document-release` because this change updates a public entry surface and
  its evidence. Apply only findings that are in scope and supported by the actual
  diff. Do not let the audit rewrite immutable release documents or expand into a
  version release.

- [ ] **Step 5: Run GREEN and commit**

  ```bash
  uv run pytest -q \
    tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  uv run python scripts/verify_release.py --tree-mode development
  git diff --check
  git add \
    README.md \
    README_CN.md \
    DESIGN.md \
    docs/README.md \
    docs/design/demo-storyboard.md \
    docs/design/route-map.md \
    docs/superpowers/plans/2026-07-22-chinese-first-portfolio-presentation.md \
    docs/superpowers/plans/2026-07-23-high-end-portfolio-entry.md \
    tests/architecture/test_documentation_governance.py \
    tests/unit/test_release_surface.py
  git diff --cached --check
  git commit -m "docs: publish the high-end portfolio evidence"
  ```

---

### Task 7: Run visual review, full verification, and local handoff

**Files:**

- Modify only files required by verified in-scope findings.
- Do not create a version bump, tag, release, deployment, or provider artifact.

- [ ] **Step 1: Run `design-review`**

  Review the real implementation, not the frozen HTML prototype, at:

  - 1440 × 1000;
  - 768 × 1024;
  - 390 × 844;
  - 320 × 720;
  - default Chinese;
  - explicit English;
  - reduced motion.

  Compare against the approved design direction:

  - deep midnight/navy, ivory, champagne;
  - student-first thesis;
  - cinematic but legible backdrop;
  - full desktop route and compact mobile/tablet summary;
  - continuous second-section trajectory;
  - no generic marketing cards or cheap decorative effects.

  Fix verified P1/P2 findings with RED -> GREEN. Do not reopen approved product copy
  or introduce new visual concepts without a real usability/accessibility defect.

- [ ] **Step 2: Run the complete frontend and architecture gate**

  ```bash
  uv lock --check
  npm --prefix web run lint
  npm --prefix web run typecheck
  npm --prefix web run test
  npm --prefix web run build
  uv run ruff check .
  uv run pyright
  ```

- [ ] **Step 3: Run complete repository verification**

  ```bash
  make doctor MODE=dev
  make check
  make proof
  make compose-proof
  make down
  docker compose ps --all
  uv run python scripts/verify_release.py --tree-mode development
  ```

  Required:

  - every command exits 0;
  - exact top-level `make compose-proof` exits 0;
  - no task-owned Compose residue;
  - current retained volume is preserved;
  - no new dependency/lockfile/migration/API/BFF diff.

- [ ] **Step 4: Review the exact base-to-HEAD diff**

  ```bash
  git diff --check "$(git merge-base HEAD origin/main)"..HEAD
  git diff --stat "$(git merge-base HEAD origin/main)"..HEAD
  git status --short
  ```

  Audit:

  - root-only visual scope;
  - demo shell unchanged except intentionally shared catalog values;
  - no dependency, lockfile, migration, API, BFF, worker, CI, or version changes;
  - no Docker change beyond the exact standalone `public` copy and its regression;
  - no private paths, design handoff metadata, credentials, secrets, raw codes,
    debug JSON, or real-person data;
  - screenshot and optimized assets are truthful;
  - published release digests remain unchanged.

- [ ] **Step 5: Record final evidence**

  Handoff must include:

  - exact base, branch, worktree, final HEAD, and ordered commits;
  - actual diff stat;
  - RED -> GREEN evidence per task;
  - asset dimensions, bytes, and SHA-256;
  - screenshot dimensions and SHA-256;
  - design-review findings and disposition;
  - full verification results;
  - Docker before/after inventory and teardown;
  - documentation impact;
  - explicit non-production/provider/release boundaries.

- [ ] **Step 6: Stop at clean local handoff**

  Do not push, create a PR, merge, tag, release, deploy, run a provider, or remove
  the branch/worktree without separate authorization.

## Verification Matrix

| Contract | Required evidence |
| --- | --- |
| Chinese-first | exact SSR heading and `html[lang=zh-CN]` |
| English parity | explicit switch, exact `en`, catalog key parity |
| static root | zero API/session/task/EventSource activity |
| student-first value | headline/subtitle and origin condition visible |
| route truth | Australia/Japan/Malaysia with reason and status |
| complete-flow CTA | exact `/demo/collaboration` href |
| focused evidence CTA | exact `/demo` href |
| route-only visual isolation | demo routes retain `PresentationShell` |
| optimized imagery | source identity plus AVIF/WebP variants |
| standalone delivery | exact non-root `public` copy plus Chromium decode |
| responsive | 320/390/768/1440, no clipping/overflow |
| accessibility | one H1, landmarks, skip link, focus, 44px targets |
| reduced motion | all content visible without animated completion |
| truthful screenshot | real Compose Chromium PNG, 1440px wide |
| docs governance | current status, unchanged historical release digests |
| repository safety | no dependency/lockfile/migration/API/BFF/version drift |
| teardown | task Compose resources absent; retained data preserved |

## Expected Commit Sequence

1. `feat: freeze the high-end portfolio contract`
2. `feat: add responsive voyage imagery`
3. `feat: add the cinematic portfolio route`
4. `feat: add the portfolio decision journey`
5. `test: prove the high-end portfolio entry`
6. `docs: publish the high-end portfolio evidence`
7. Only if required: one focused follow-up commit for verified authority/design
   findings; do not amend reviewed commits unless explicitly instructed.

## Explicit Non-Goals

- No school search or recommendation engine.
- No new data source, live institutional coverage, DRA call, or provider proof.
- No real-student onboarding or profile form.
- No authentication, analytics, CRM, lead capture, upload, contact, or payment.
- No backend, authority, migration, API/BFF, worker, task, SSE, Skill, receipt, or
  planning behavior change.
- No design-system rewrite for the two demo routes.
- No font download, icon pack, component library, motion library, WebGL, or video.
- No release/version bump, tag, GitHub Release, deployment, or public hosting.
- No rewrite of v0.1.0/v0.1.1/v0.1.2 release artifacts.

## Completion Definition

This plan is complete only when:

1. the implemented root is recognizably the approved A3 “虚幻夜航” direction;
2. a non-technical Chinese reviewer can identify what the product does, why
   Australia is recommended, what the alternatives mean, and where to start;
3. both demo routes retain their existing verified visual and authority behavior;
4. the root performs zero product-side network/session/task effects;
5. optimized responsive imagery, four viewport classes, English parity,
   accessibility, and reduced motion are executable gates;
6. the real Compose Chromium lane refreshes and validates the public screenshot;
7. docs accurately distinguish the new unreleased root from immutable v0.1.2
   history;
8. full repository and Compose verification pass;
9. the branch is clean and stopped for independent authority review.
