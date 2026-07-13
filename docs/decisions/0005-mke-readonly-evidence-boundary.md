# ADR 0005: MKE read-only Evidence boundary

Status: Accepted

Implementation status: Not started

M4B establishes these authority decisions:

1. Night Voyager consumes only an exact reviewed MKE candidate wheel through the public
   v1 stdio MCP tools. It does not import MKE internals or build from a moving checkout.
2. The checked-in candidate lock, upstream same-wheel proof receipt, and delivered wheel
   bytes jointly define artifact identity. Caller-supplied files cannot establish trust.
3. MKE owns locator-bearing candidate provenance. Night Voyager owns tenant, source-pack,
   exact claim, `EvidenceRole`, source identity, freshness, candidate authority,
   acceptance, planning, and human decision semantics.
4. MKE opaque IDs remain trace data. Night Voyager creates deterministic UUIDv5 Evidence
   identity from its own tenant/pack/source/claim/locator/text-hash projection.
5. Every projected result remains `EvidenceAuthority.UNTRUSTED_CANDIDATE`. M4B provides
   no persistence or promotion path and cannot create a PlanningRun or Case transition.
6. General no-match is store-level only. Pack-level no-match exists only as a
   proof-controller assertion inside an owned one-source disposable store and is never a
   real-world negative claim.
7. The MCP SDK is an isolated optional dependency. The default evaluator, worker,
   Compose profile, installed-wheel proof, and required CI remain MKE-free.
8. The verifier and consumer may clean only temporary state and processes they own.
   Cleanup failure is terminal and overrides an earlier public failure.
9. M4B does not implement `PlanningAdapter` or join the M4A task path. Any Evidence
   acceptance, MKE-backed planning, or visible integration requires a later decision.

## Consequences

M4B adds strict consumer-owned v1 response models, a read-only consumer port, an official
MCP SDK stdio adapter, a source-pack projector, an immutable candidate lock, and one
bounded real candidate smoke. Runtime request data cannot choose executable, environment,
store, artifact, tenant, claim, authority, timeout, or cleanup scope.

The project gains a reproducible compatibility signal without adding a second domain
authority or changing the deterministic product path. Candidate acquisition may be a
durable public URL or an explicit maintainer handoff. If exact bytes are unavailable, the
real proof stops rather than rebuilding a substitute.

## Rejected alternatives

A full Night Voyager-owned MKE conformance platform is rejected because MKE already owns
generic schema, lifecycle, portability, and installed-wheel proof. A runtime-selectable
MKE `PlanningAdapter` is rejected because read Evidence does not supply the complete
cost, ranking, policy, and authority inputs required for planning. Source-checkout builds
are rejected because they do not establish reviewed artifact identity. Required
cross-repository CI is rejected because upstream availability and artifact retention must
not block the default Night Voyager profile.

M4B is intentionally time-boxed. After completion, the project must explicitly continue
to a governed acceptance/visible-integration gate or remove the optional adapter.
