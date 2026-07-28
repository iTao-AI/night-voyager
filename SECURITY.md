# Security Policy

## Supported versions

Night Voyager v0.1.3 is a local synthetic portfolio release with Governed Collaboration Core v1, explicit fact-to-plan authority, Chinese-first bilingual presentation, the High-End Portfolio Entry, and deterministic offline governed DRA capability. Security fixes apply to the current default branch; the release is not supported as a production service.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

The current development web lock uses Next.js and `eslint-config-next` `16.2.12` as an independent patch-maintenance update. A root npm override resolves transitive PostCSS to `8.5.18`; fresh local audits therefore no longer report the PostCSS advisories behind Dependabot alerts #8 and #9, without claiming that GitHub has closed those alerts before merge.

Optional/transitive `sharp@0.34.5` still carries `GHSA-f88m-g3jw-g9cj` through Next.js and remains a deferred risk; the repository does not add direct `sharp` or force an unsupported `sharp@0.35.x` override. A full development audit may also retain the dev-only `brace-expansion -> minimatch -> ESLint toolchain` advisory root. This development state is explicitly not an audit-zero claim.
