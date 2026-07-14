"""Product-owned read-only port for an MKE evidence consumer."""

from __future__ import annotations

from typing import Protocol

from night_voyager.evidence.mke_contract import (
    AskLibraryResponseV1,
    ListLibrariesResponseV1,
    SearchLibraryResponseV1,
)
from night_voyager.evidence.mke_models import EvidenceQuery


class EvidenceConsumer(Protocol):
    async def initialize(self) -> ListLibrariesResponseV1: ...

    async def search(self, query: EvidenceQuery) -> SearchLibraryResponseV1: ...

    async def ask(self, query: EvidenceQuery) -> AskLibraryResponseV1: ...

    async def aclose(self) -> None: ...
