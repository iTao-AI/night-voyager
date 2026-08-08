# Security Policy

## Supported versions

Night Voyager v0.1.5 is a local synthetic portfolio release with the prior portfolio workflow plus governed timeline execution, recovery/reassessment authority, reconciliation, and evaluator-first presentation. Security fixes apply to the current default branch; the release is not supported as a production service.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Local-release guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.

The current development web manifest and lock use Next.js and `eslint-config-next` `16.3.0`, with `postcss@8.5.23` and compatible transitive `nanoid@3.3.18`. The repository has no direct postcss, nanoid, or sharp dependency and no npm override. Dependabot hosted alert status is a post-merge read-only gate; this local change makes no hosted alert claim.

The Python runtime graph for the optional `mke` extra resolves `cryptography==50.0.0` transitively through `mcp` and `PyJWT[crypto]`. This is the first patched version for Dependabot alert #14 (`GHSA-g6cj-pr64-35w5` / `CVE-2026-69247`). The local graph is outside the affected range; hosted alert closure is evaluated only after merge and is not claimed by local validation. Post-merge GitHub readback remains mandatory. A source and test scan found no Night Voyager use of cryptography's PKCS#7 decryption or finite-field Diffie-Hellman APIs, so this upgrade requires no product compatibility shim.

Next.js resolves optional/transitive `sharp 0.35.3`, outside `GHSA-f88m-g3jw-g9cj`. Fresh full and runtime/omit-dev npm audits report zero advisory objects, including no sharp advisory object. The immutable v0.1.5 release was not an audit-zero claim, and its historical release evidence remains unchanged. Dependabot #7 hosted alert status is evaluated after merge; this local change makes no hosted alert claim.
