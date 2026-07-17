# M2 Identity, Session, and RLS Implementation Plan

**Implementation status:** Complete. The steps below preserve the historical
implementation record.

1. Freeze dependency, migration-head, role-init, ADR, API, operations, and
   milestone-boundary contracts.
2. Add fresh-volume roles, async Alembic migration, forced tenant RLS,
   restricted authentication functions, and catalog verification.
3. Implement and unit-test the role matrix, tokens, digests, Origin/CSRF policy,
   expiry, and fail-closed configuration.
4. Implement and integration-test repository, service, request identity, and
   demo session HTTP endpoints.
5. Prove two-tenant isolation, least privilege, forced owner checks, spoofing
   rejection, and size-one pool cleanup using real PostgreSQL 18 roles.
6. Integrate `make db-check` into required local and hosted verification, update
   public documentation, run fresh full checks, review the diff, and commit.

Every behavioral step records an observed failing test before the minimal
implementation and a passing result afterward. Work stops before frontend
integration or later milestone artifacts.
