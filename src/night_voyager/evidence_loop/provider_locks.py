"""Exact immutable producer identities for Slice 0."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class NightVoyagerLockV1(FrozenModel):
    repository: Literal["https://github.com/iTao-AI/night-voyager"]
    release: Literal["v0.1.5"]
    ref_kind: Literal["tag"]
    tag_object: Literal["44000702c75fa3002e12245b8d7f762b564db944"]
    commit: Literal["3a82721a86f65353b849e9ee93050912d0cb079a"]
    tree: Literal["bbe32e5629b2758421d80598dbca1c795934fcb5"]
    migration_head: Literal["0015"]


class MkeLockV1(FrozenModel):
    repository: Literal["https://github.com/iTao-AI/multimodal-knowledge-engine"]
    release: Literal["v0.1.5"]
    ref_kind: Literal["tag"]
    tag_object: Literal["1ca0a0b348638369e8407270ca5f363b0e551a9e"]
    commit: Literal["d258c10dc40bd9eccd67c858b56f4e4cf5fe4610"]
    source_archive_basename: Literal["mke-v0.1.5-source.tar.gz"]
    source_archive_sha256: Literal[
        "7046ab1a6a3a0336472ef114c95b11a6b94cea0b083f2b025a96b994c1cab4bc"
    ]
    wheel_basename: Literal["multimodal_knowledge_engine-0.1.5-py3-none-any.whl"]
    wheel_sha256: Literal[
        "4c2da1a84871e1865b05a720c6ef7b7d2122ed570ec8eb0035627493ba96d281"
    ]
    tool_schema_sha256: Literal[
        "48b3b6c3a8d17af460ceff23ae64e619486f5792eb77b35416841e73a8190561"
    ]
    tools: list[Literal["search_library_v2", "read_evidence_v1"]]


class DraLockV1(FrozenModel):
    repository: Literal["https://github.com/iTao-AI/decision-research-agent"]
    release: Literal["v0.1.8"]
    ref_kind: Literal["tag"]
    tag_object: Literal["f828606741f636bca7ddbb66244ca60019eaa3c8"]
    commit: Literal["cb1f4660ee4ac7d81b04ffea014362e933487e61"]
    source_archive_basename: Literal["dra-v0.1.8-source.tar.gz"]
    source_archive_sha256: Literal[
        "ab9deaf7678571b2dda6e8275fcfe2ff69d6baab04f3ab66f84c6abdcb2a6e7f"
    ]
    consumer_contract_schema: Literal["dra.downstream-consumer.v1"]
    consumer_fixture_sha256: Literal[
        "cc602576115ff9b41b0f07fa5f6ee88db15424760a78ab4611675e62e19a8157"
    ]
    profile_id: Literal["generic-strict-citation"]
    profile_version: Literal["1"]


class ProviderLockSetV1(FrozenModel):
    schema_version: Literal["night-voyager.evidence-loop-provider-locks.v1"]
    night_voyager: NightVoyagerLockV1
    mke: MkeLockV1
    dra: DraLockV1
