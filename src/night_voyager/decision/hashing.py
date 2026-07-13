from __future__ import annotations

import hashlib
import json


def canonical_request_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: item.value,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
