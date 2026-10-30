# Security Policy

## Supported versions

Night Voyager v0.1.6 is a local synthetic portfolio release; it is provider-free and not deployed. It includes the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and evaluator-first presentation. It is not supported as a production service. Security fixes apply to the current default branch.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

## Current development dependency snapshot

As of 2026-10-30, the default-branch manifest and lock use Next.js and `eslint-config-next` `16.3.6`, with `postcss@8.5.23`, compatible transitive `nanoid@3.3.18`, and optional/transitive sharp 0.35.4. The repository has no direct postcss, nanoid, or sharp dependency and no npm override. The nanoid contract permits security patches within `3.3.x` at or above `3.3.18`; it rejects downgrades and unreviewed minor or major lines. Direct framework pins and lockfile consistency checks remain in place.

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

Current source locks `source-map-js` to `1.2.2` for `GHSA-68fv-2mgg-jv7q`, with a minimum-version contract that rejects the affected `1.2.1` graph. This source change does not itself close a hosted alert. The table is the dated default-branch inventory before that change, not a fresh npm audit or completed remediation of every listed advisory. Other dependency updates, their compatibility verification, and GitHub post-merge alert readback remain pending. Re-query the default branch before selecting an update; an older green CI run or closed alert does not establish the current security state.

## Historical security records

GitHub readback on 2026-08-30 recorded zero open Dependabot alerts on the default branch. This is a point-in-time default-branch readback, not a permanent audit-zero claim. Dependabot #7 (`sharp`, `GHSA-f88m-g3jw-g9cj`) was fixed with `fixed_at=2026-08-08T09:16:53Z` and no dismissal fields.

The earlier optional `mke` security update resolved `cryptography==50.0.0` transitively through `mcp` and `PyJWT[crypto]`. This was the first patched version for Dependabot alert #14 (`GHSA-g6cj-pr64-35w5` / `CVE-2026-69247`), fixed with `fixed_at=2026-08-08T11:18:13Z`. Neither Dependabot alert #7 nor #14 was dismissed; both had no dismissal fields in that readback. Local package/audit validation did not fix or dismiss GitHub alerts; GitHub post-merge analysis recorded the fixed states. The source and test scan for that update found no Night Voyager use of cryptography's PKCS#7 decryption or finite-field Diffie-Hellman APIs, so it required no product compatibility shim.

An earlier Next.js dependency graph resolved optional/transitive sharp 0.35.3, outside `GHSA-f88m-g3jw-g9cj`. The historical full and runtime/omit-dev npm audits reported zero advisory objects, including no sharp advisory object. These dated results do not describe the current graph or its open alerts above. The immutable v0.1.5 release was not an audit-zero claim, and its historical release evidence remains unchanged.
