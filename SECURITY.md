# Security Policy

## Supported versions

Night Voyager v0.1.5 is a local synthetic portfolio release with the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and evaluator-first presentation. Security fixes apply to the current default branch; the release is not supported as a production service.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

The current web lock uses Next.js and `eslint-config-next` `16.2.12`. A root npm override resolves transitive PostCSS to `8.5.18`; GitHub Dependabot alerts #8 and #9 are `FIXED`.

Optional/transitive `sharp@0.34.5` still carries `GHSA-f88m-g3jw-g9cj` through Next.js; Dependabot alert #7 remains `OPEN` and deferred. The repository does not add direct `sharp` or force an unsupported `sharp@0.35.x` override. A full development audit also retains the dev-only `brace-expansion -> minimatch -> ESLint toolchain` advisory root. This release is explicitly not an audit-zero claim.
