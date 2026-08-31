#!/usr/bin/env python3
"""Fail-closed validation for a release tar archive before extraction."""

from __future__ import annotations

import argparse
import posixpath
import tarfile
from collections.abc import Iterable
from pathlib import Path


def _validate_expected_root(expected_root: str) -> str:
    if (
        not expected_root
        or expected_root in {".", ".."}
        or "/" in expected_root
        or "\\" in expected_root
    ):
        raise ValueError("expected root must be one relative path component")
    return expected_root


def _canonical_member_name(member: tarfile.TarInfo) -> str:
    name = member.name
    if not name or "\x00" in name or "\\" in name:
        raise ValueError(f"unsafe archive member name: {name!r}")
    if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        raise ValueError(f"unsafe archive member name: {name!r}")

    canonical = name.rstrip("/")
    if not canonical or canonical != posixpath.normpath(canonical):
        raise ValueError(f"unsafe archive member path: {name!r}")
    if any(part in {"", ".", ".."} for part in canonical.split("/")):
        raise ValueError(f"unsafe archive member path: {name!r}")
    if name.endswith("/") and not member.isdir():
        raise ValueError(f"unsafe archive member shape: {name!r}")
    if not (member.isdir() or member.isfile()):
        raise ValueError(f"unsafe archive member shape: {name!r}")
    return canonical


def validate_members(members: Iterable[tarfile.TarInfo], expected_root: str) -> None:
    """Validate archive members without touching the filesystem."""

    expected_root = _validate_expected_root(expected_root)
    member_list = list(members)
    if not member_list:
        raise ValueError("archive is empty")

    seen: set[str] = set()
    top_level: set[str] = set()
    root_seen = False
    for member in member_list:
        canonical = _canonical_member_name(member)
        if canonical in seen:
            raise ValueError(f"duplicate archive member: {canonical!r}")
        seen.add(canonical)

        parts = canonical.split("/")
        if ".git" in parts:
            raise ValueError(f"unsafe .git archive member: {member.name!r}")
        top_level.add(parts[0])
        if canonical == expected_root:
            if not member.isdir():
                raise ValueError("expected archive root must be a directory")
            root_seen = True

    if top_level != {expected_root}:
        raise ValueError(
            f"archive must contain exactly one expected root {expected_root!r}; "
            f"found {sorted(top_level)!r}"
        )
    if not root_seen:
        raise ValueError(f"archive is missing expected root {expected_root!r}")

    prefix = f"{expected_root}/"
    outside = [
        member_name
        for member_name in seen
        if member_name != expected_root and not member_name.startswith(prefix)
    ]
    if outside:
        raise ValueError(f"archive member outside expected root: {outside[0]!r}")


def validate_archive(path: Path, expected_root: str) -> None:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            validate_members(archive.getmembers(), expected_root)
    except (OSError, tarfile.TarError) as error:
        raise ValueError(f"cannot read archive: {error}") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-root", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        validate_archive(args.archive, args.expected_root)
    except ValueError as error:
        raise SystemExit(f"release archive rejected: {error}") from error
    print(f"release archive members validated: {args.expected_root}/")


if __name__ == "__main__":
    main()
