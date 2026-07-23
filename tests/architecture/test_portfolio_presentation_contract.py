from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/assets/design/night-voyager-voyage-source.png"
SOURCE_SHA256 = "4fe73754e5180e725bfc7d734fc9a9039030da5ebef41f31aa1cf2f1ccff55fc"
SOURCE_BYTES = 1_662_495
SOURCE_SIZE = (1672, 941)
PRIVATE_OR_METADATA_MARKERS = (
    b"/Users/",
    b".gstack",
    b"Career",
    b"Exif",
    b"EXIF",
    b"XMP ",
    b"http://ns.adobe.com/xap/",
)
PRODUCTION_ASSETS = (
    (
        "web/public/portfolio/night-voyager-voyage-960.avif",
        "avif",
        (960, 540),
        "c8850328b09d17fe70f67fadc8a489bff94a5008af33436b4416a958129de028",
    ),
    (
        "web/public/portfolio/night-voyager-voyage-1680.avif",
        "avif",
        (1672, 941),
        "41bdfcc5065c3d8cfa454005875f97e1a1befe4f49e6cfd239433e6c61a1edfc",
    ),
    (
        "web/public/portfolio/night-voyager-voyage-960.webp",
        "webp",
        (960, 540),
        "5dffa4256d757f0fbe05b401b0679fe11e5863ebeee4f06a212a8f81aa0d9ded",
    ),
    (
        "web/public/portfolio/night-voyager-voyage-1680.webp",
        "webp",
        (1672, 941),
        "a5f71dca693e58916876a6f126d35c41aeaf21608935fe8c89b6dab09d5de806",
    ),
)
LOCKED_DEPENDENCY_IDENTITIES = {
    "pyproject.toml": "0c45b4c3a5ef864c778cfd52157cabe9492462a7722047c31289c79e5a2e373f",
    "uv.lock": "ea3a84481aa2e47e7f5fcd31e33386ee568105e3194b72960d7198082a0845d5",
    "web/package.json": "d3a5d1f6f7d7c7d9d3b346eba4c9214ec9d39aa17d5cf634b4f80dfcc4632587",
    "web/package-lock.json": (
        "2f8be22c4c80ec32e0057a0dc1d02b44e9f756294e756b4fae79bbab58db00da"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _avif_size(data: bytes) -> tuple[int, int]:
    assert data[4:8] == b"ftyp"
    assert b"avif" in data[8:32]
    marker = data.find(b"ispe")
    assert marker >= 4
    return (
        int.from_bytes(data[marker + 8 : marker + 12], "big"),
        int.from_bytes(data[marker + 12 : marker + 16], "big"),
    )


def _webp_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"RIFF")
    assert data[8:12] == b"WEBP"
    chunk = data[12:16]
    payload = 20
    if chunk == b"VP8X":
        return (
            1 + int.from_bytes(data[payload + 4 : payload + 7], "little"),
            1 + int.from_bytes(data[payload + 7 : payload + 10], "little"),
        )
    if chunk == b"VP8 ":
        assert data[payload + 3 : payload + 6] == b"\x9d\x01\x2a"
        return (
            int.from_bytes(data[payload + 6 : payload + 8], "little") & 0x3FFF,
            int.from_bytes(data[payload + 8 : payload + 10], "little") & 0x3FFF,
        )
    assert chunk == b"VP8L"
    assert data[payload] == 0x2F
    packed = int.from_bytes(data[payload + 1 : payload + 5], "little")
    return (packed & 0x3FFF) + 1, ((packed >> 14) & 0x3FFF) + 1


def test_approved_source_identity_is_exact() -> None:
    assert SOURCE.is_file()
    data = SOURCE.read_bytes()
    assert len(data) == SOURCE_BYTES
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256
    assert _png_size(data) == SOURCE_SIZE
    assert all(marker not in data for marker in PRIVATE_OR_METADATA_MARKERS)


@pytest.mark.parametrize(
    ("relative", "format_name", "expected_size", "expected_sha256"),
    PRODUCTION_ASSETS,
)
def test_responsive_production_asset_is_valid_and_bounded(
    relative: str,
    format_name: str,
    expected_size: tuple[int, int],
    expected_sha256: str,
) -> None:
    path = ROOT / relative
    assert path.is_file(), relative
    data = path.read_bytes()
    assert 0 < len(data) < SOURCE_BYTES
    assert hashlib.sha256(data).hexdigest() == expected_sha256
    width, height = (
        _avif_size(data) if format_name == "avif" else _webp_size(data)
    )
    assert (width, height) == expected_size
    assert height > 0
    assert abs((width / height) - (SOURCE_SIZE[0] / SOURCE_SIZE[1])) < 0.002
    assert all(marker not in data for marker in PRIVATE_OR_METADATA_MARKERS)


def test_runtime_portfolio_directory_contains_no_png_source() -> None:
    runtime_directory = ROOT / "web/public/portfolio"
    assert not runtime_directory.exists() or not any(runtime_directory.glob("*.png"))


def test_dependency_manifests_and_locks_keep_the_approved_identity() -> None:
    for relative, expected_sha256 in LOCKED_DEPENDENCY_IDENTITIES.items():
        assert _sha256(ROOT / relative) == expected_sha256, relative
