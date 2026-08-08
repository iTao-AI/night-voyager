# Security Policy

## Supported versions

Night Voyager v0.1.5 is a local synthetic portfolio release with the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and evaluator-first presentation. Security fixes apply to the current default branch; the release is not supported as a production service.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

The current development web manifest and lock use Next.js and `eslint-config-next` `16.3.0`. A root npm override resolves transitive PostCSS to `8.5.18`; GitHub Dependabot alerts #8 and #9 are `FIXED`.

Next.js resolves optional/transitive `sharp 0.35.3`, outside `GHSA-f88m-g3jw-g9cj`. The repository has no direct sharp dependency or override. The immutable v0.1.5 release was not an audit-zero claim, and its historical release evidence remains unchanged. Dependabot #7 hosted alert status is evaluated after merge; this local change makes no hosted alert claim. Fresh runtime/full audit evidence retains the approved `postcss@8.5.18` -> `nanoid@3.3.16` advisory path and the dev-only `brace-expansion -> minimatch -> ESLint toolchain` advisory root. This is not an audit-zero claim.
