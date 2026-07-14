# MKE read-only consumer reference

M4B is an optional, local, synthetic, read-only compatibility boundary. It consumes one
exact reviewed MKE wheel through the public v1 stdio MCP tools and maps locator-bearing
results to a Night Voyager source manifest. Every result remains
`EvidenceAuthority.UNTRUSTED_CANDIDATE`.

## Public tools and responses

The adapter requires `list_libraries_v1`, `search_library_v1`, and `ask_library_v1`.
Search requires `query`, Ask requires `question`, and both calls always send the literal
`limit=1`. Extra optional tool inputs are compatible; renamed tools or new required inputs
fail closed.

Responses must use the exact `mke.list_libraries_response.v1`,
`mke.search_library_response.v1`, and `mke.ask_library_response.v1` schemas. The consumer
validates opaque IDs, fingerprint, Publication revision, Run trace, locator, selected text,
active-store counts, and Search/Ask consistency before projection.

## Night Voyager authority

MKE owns producer contract, store-local trace, Publication/Run provenance, fingerprint,
locator, and selected text. Night Voyager owns organization, source pack and entry, exact
claim, `EvidenceRole`, source snapshot, freshness, authority, acceptance, planning, and
human decision.

The projector derives local UUIDv5 identity only from Night Voyager-owned organization,
pack, source, claim, role, locator, and selected-text hash. MKE opaque IDs remain trace
data. The adapter does not persist or promote Evidence, create a PlanningRun, transition a
Case, or implement `PlanningAdapter`.

Active-store zero results produce `CandidateStoreNoMatch`. Only the disposable one-source
proof may strengthen that observation to its internal `proof_pack_no_match` assertion; it
is not a real-world negative claim.

## Isolation and bounds

`mcp>=1.28.1,<2` is an optional extra locked at `1.28.1`. Default pytest, `make check`,
Compose, API, worker, SSE, frontend, `/demo`, and installed-wheel proof do not install or
import it. The process adapter has fixed startup/tool deadlines, response/text/stderr
bounds, trusted executable and paths, an allowlisted child environment, and SDK-owned
stdin-close/terminate/kill cleanup.

Use the [candidate proof runbook](../operations/mke-candidate-proof.md) for maintainer
commands. Evaluators do not need MKE or candidate bytes.
