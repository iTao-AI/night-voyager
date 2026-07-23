# Security Policy

## Supported versions

Night Voyager v0.1.3 is a local synthetic portfolio release with Governed Collaboration Core v1, explicit fact-to-plan authority, Chinese-first bilingual presentation, the High-End Portfolio Entry, and deterministic offline governed DRA capability. Security fixes apply to the current default branch; the release is not supported as a production service.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

The web lock uses Next.js and `eslint-config-next` `16.2.11`, closing the direct advisories listed for that Next.js release. Optional/transitive `sharp@0.34.5` still carries `GHSA-f88m-g3jw-g9cj`; this deferred risk is not an audit-zero claim, and the repository does not force an unsupported `sharp@0.35.x` override.
