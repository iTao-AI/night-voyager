from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel


def canonical_json_bytes(value: object) -> bytes:
    projection = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
