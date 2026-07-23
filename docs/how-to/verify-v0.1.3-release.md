# Verify the Night Voyager v0.1.3 Release

This procedure verifies the `local synthetic portfolio release`: explicit planning-start authority, the same-Case fact-to-plan walkthrough, exact `zh-CN` / `en` presentation behavior, the static High-End Portfolio Entry, and the Next.js 16.2.11 security patch. It does not deploy Night Voyager, call a live provider, connect live DRA/MKE product paths, or validate production behavior.

## 1. Verify merged-main identity

```bash
git fetch origin --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git describe --tags --exact-match HEAD
```

Expected after publication: a clean `main`, identical `HEAD` and `origin/main`, and exact tag `v0.1.3`.

## 2. Verify the annotated tag

```bash
git cat-file -t v0.1.3
git rev-parse v0.1.3^{tag}
git rev-parse v0.1.3^{commit}
```

Expected: object type `tag`; the peeled commit equals the verified release commit. Never move the tag after publication.

## 3. Verify the release gates

Run these commands from the clean reviewed release tree:

```bash
make doctor MODE=dev
uv lock --check
uv run pytest -q tests/architecture/test_v0_1_3_release_contract.py tests/architecture/test_documentation_governance.py tests/unit/test_release_surface.py
uv run ruff check .
uv run pyright
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
make collaboration-check
make skills-check
make dra-check
make db-check
make check
make proof
make compose-proof
make down
docker compose ps --all
uv run python scripts/verify_release.py --tree-mode release
git diff --check
```

Expected: every command exits successfully, final Compose state is empty, and the release verifier confirms current `v0.1.3` identity plus all six immutable historical documents. Live provider proof is intentionally excluded.

## 4. Verify the public source archive

```bash
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.3.tar.gz"
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.3.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
tar -xzf "$archive" -C "$tmp_dir"
cd "$tmp_dir/night-voyager-0.1.3"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all proof commands pass; final Compose state is empty. Use the extracted source archive, not the development `.venv`, `node_modules`, retained demo volume, or a custom wheel.

## 5. Failure handling

If merged-main, hosted checks, tag identity, archive identity, release contracts, browser flows, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not force-move `v0.1.3`, replace the archive, bypass the `main` ruleset, run an unauthorized live provider proof, or describe a failed gate as successful.
