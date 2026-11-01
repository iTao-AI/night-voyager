# Security Policy

## Supported versions

Night Voyager v0.1.6 is a local synthetic portfolio release; it is provider-free and not deployed. It includes the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and evaluator-first presentation. It is not supported as a production service. Security fixes apply to the current default branch.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

## Current development dependency snapshot

As of 2026-11-01, the current development manifest and lock use Next.js and `eslint-config-next` `16.4.3`, with React and React DOM `19.2.9`, `postcss@8.5.23`, compatible transitive nanoid on the approved `3.3.x` line, and optional/transitive sharp 0.35.5. Frontend development tooling uses Vite `8.1.6`, aligned Vitest packages `4.1.12`, and transitive Zod `4.6.6` in the ESLint tooling graph. The repository has no direct postcss, nanoid, or sharp dependency and no npm override. The nanoid contract permits security patches within `3.3.x` at or above `3.3.18`; it rejects downgrades and unreviewed minor or major lines. Direct framework pins and lockfile consistency checks remain in place.

The compatible security revisions cover the original snapshot and newer audit findings: [Next.js 16.4.1](https://github.com/vercel/next.js/releases/tag/v16.4.1), [sharp 0.35.5 / librsvg](https://github.com/lovell/sharp/security/advisories/GHSA-wq5f-xc86-pv6w), [Vite 8.1.6](https://github.com/vitejs/vite/security/advisories/GHSA-rq7h-c2jc-7f22), and [Vitest mocker 4.1.12](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8). Subsequent maintenance aligns the Next.js family on the [16.4.3 patch](https://github.com/vercel/next.js/releases/tag/v16.4.3) and React on [19.2.9](https://github.com/react/react/releases/tag/v19.2.9). They retain the existing framework major versions. Vite and Vitest alerts concern developer tooling, while Next.js includes both runtime and `next dev` conditions; installing a vulnerable package does not by itself establish an exploitable product route.

During maintenance on 2026-10-31, an npm audit of the intermediate Next.js `16.3.8` graph still reported one critical runtime package entry covering three newer advisories. Their first patched 16.x revision was `16.4.1`, now superseded by the compatible patch above; the image-optimization advisory also documents sharp `>=0.35.5` as a workaround. The Server Actions and typed-array `use cache` conditions were not present in application source, but that absence was not used to retain the affected framework revision. The same audit reported development-tool findings involving minimatch and Zod. Zod is now `4.6.6`, the first patched version for [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5), within its existing major and parent dependency range. The minimatch/toolchain findings remain a separate maintenance item; this update is not a complete-remediation or audit-zero claim.

After these updates, the 2026-10-31 `npm audit --omit=dev` readback reported zero runtime advisory entries. The full npm audit still reported 16 moderate development package entries in the minimatch toolchain. These are point-in-time npm results, separate from Python optional dependencies and GitHub's alert state; no cross-major override or framework replacement was used to remove the remaining findings.

The Python runtime explicitly requests SQLAlchemy's `asyncio` extra so that its existing asynchronous engine and session code receives the locked `greenlet` dependency on all supported platforms, including Apple Silicon. This keeps SQLAlchemy `2.0.52` and greenlet `3.5.3`; it changes dependency selection rather than the database or application contract. See the [SQLAlchemy 2.0 platform installation notes](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#asyncio-platform-installation-notes-including-apple-m1).

The [Dependabot alert inventory](https://github.com/iTao-AI/night-voyager/security/dependabot) read on 2026-10-30 contained **21 open alert records**: 5 high, 13 medium, and 3 low, covering 16 distinct advisories. Manifest and lockfile alerts can represent the same advisory. The affected locked packages and the first patched versions reported by those advisories are:

| Package | Locked version at default-branch readback | Advisory patched version | Dependency lane |
| --- | --- | --- | --- |
| `next` | `16.3.6` | `16.3.8` | Web runtime; keep the Next.js package family aligned |
| `sharp` | `0.35.4` | `0.35.5` | Optional web runtime |
| `source-map-js` | `1.2.1` | `1.2.2` | Transitive web dependency |
| `vite` | `8.1.4` | `8.1.6` | Frontend development tooling |
| `@vitest/mocker` | `4.1.11` | `4.1.12` | Frontend tests; keep Vitest packages aligned |
| `mcp` | `1.28.1` | `1.30.0` | Separately enabled `mke` extra |
| `Mako` | `1.3.12` | `1.4.2` | Migration dependency |

Current source already locks `source-map-js` to `1.2.2` for `GHSA-68fv-2mgg-jv7q`, with a minimum-version contract that rejects the affected `1.2.1` graph. It now also contains the Next.js, sharp, Vite and Vitest revisions above. These source changes do not themselves close hosted alerts. The table is the dated default-branch inventory before those changes, not a fresh npm audit or completed remediation of every listed advisory. GitHub post-merge alert readback remains a separate check; do not manually dismiss an alert merely because the lock is patched.

The 2026-11-01 maintenance also locks optional MCP to `1.30.0`, Mako to `1.4.2`, and certifi to `2026.10.19`. The MCP adapter uses a stdio client rather than a stateful StreamableHTTP server, but [GHSA-rwrf-2pqf-9j8j](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-rwrf-2pqf-9j8j) also affects clients over stdio: a server-chosen tool output schema could make the SDK fetch external references. MCP `1.30.0` restricts that resolution to the schema document and standard metaschemas. The adapter retains the existing 1.x API and Night Voyager-owned read-only contracts. Mako's compatible update fixes the Windows `TemplateLookup` traversal described by [GHSA-5639-2j2p-m4mx](https://github.com/sqlalchemy/mako/security/advisories/GHSA-5639-2j2p-m4mx); the repository still uses only a fixed Alembic template. No database schema changes are involved.

For [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2), certifi `2026.10.18` first removed emSign roots after intermediate key compromise. The selected `2026.10.19` keeps the affected `emSign ECC Root CA - G3` removed and restores unaffected emSign roots. Dependency synchronization and image rebuilds must use the updated lock to receive this trust-store change. Routine tooling patches are pyright `1.1.414`, pytest-asyncio `1.4.1`, and the SHA-pinned `actions/upload-artifact` `v7.0.2`.

The remaining minimatch finding [GHSA-g3hv-75wg-m249](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249) requires an attacker-controlled glob with `optimizationLevel >= 2`. Both locked copies (`3.1.5` and `10.2.5`) are development-only; application routes do not import minimatch or accept glob patterns for it. ESLint uses repository-controlled patterns. The 2026-11-01 review of the two failed Dependabot runs found `security_update_not_possible`: the highest resolvable version was `10.2.5`, while the alert requires `>=11.0.1`. ESLint and its plugins still require the 3.x line, and typescript-estree requires `^10.2.2`. These were updater failures, not failures of the product CI workflow. The same day's updated graph reported zero runtime entries with `npm audit --omit=dev` and 16 moderate development package entries in the full audit. Keep the finding open for a compatible parent-toolchain update; do not force a cross-major override, dismiss the alert, or repeatedly rerun the unchanged updater. Re-query the default branch before selecting an update, since an older green CI run or closed alert does not establish the current security state.

## Historical security records

GitHub readback on 2026-08-30 recorded zero open Dependabot alerts on the default branch. This is a point-in-time default-branch readback, not a permanent audit-zero claim. The earlier approved graph included `nanoid@3.3.18`; subsequent compatible patches may differ. Dependabot #7 (`sharp`, `GHSA-f88m-g3jw-g9cj`) was fixed with `fixed_at=2026-08-08T09:16:53Z` and no dismissal fields.

The earlier optional `mke` security update resolved `cryptography==50.0.0` transitively through `mcp` and `PyJWT[crypto]`. This was the first patched version for Dependabot alert #14 (`GHSA-g6cj-pr64-35w5` / `CVE-2026-69247`), fixed with `fixed_at=2026-08-08T11:18:13Z`. Neither Dependabot alert #7 nor #14 was dismissed; both had no dismissal fields in that readback. Local package/audit validation did not fix or dismiss GitHub alerts; GitHub post-merge analysis recorded the fixed states. The source and test scan for that update found no Night Voyager use of cryptography's PKCS#7 decryption or finite-field Diffie-Hellman APIs, so it required no product compatibility shim.

An earlier Next.js dependency graph resolved optional/transitive sharp 0.35.3, outside `GHSA-f88m-g3jw-g9cj`. The historical full and runtime/omit-dev npm audits reported zero advisory objects, including no sharp advisory object. These dated results do not describe the current graph or its open alerts above. The immutable v0.1.5 release was not an audit-zero claim, and its historical release evidence remains unchanged.
