# M2 Identity, Session, and RLS Design

M2 proves the complete security path from one of three fixed synthetic actor
choices to an opaque session, restricted database bootstrap, transaction-local
`ActorContext`, and forced tenant row security under non-owner PostgreSQL roles.

The API owns Origin, CSRF, and cookie policy. A framework-independent service
coordinates a repository using one async session and one transaction. The
repository resolves digest-only sessions through restricted functions, sets
organization, actor, role, and session context with transaction-local settings,
then performs explicit bounded tenant queries.

The migration creates only organizations, actors, memberships, synthetic demo
principals, and demo sessions. No case, evidence, planning, review, decision,
task, lease, event, or SSE domain tables belong to M2.
