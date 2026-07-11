# Security Policy

## Supported versions

Night Voyager has no released production version. Security fixes apply to the current default branch during the local bootstrap phase.

## Reporting

Do not open a public issue containing credentials, private records, or exploit details. Contact the repository maintainers through a private channel and include a minimal reproduction, affected revision, and impact.

## Bootstrap guarantees

Synthetic defaults are for local development and tests only. Production mode rejects the repository's default secret. Never use `.env.example` values for a public deployment.
