# Verify the Night Voyager v0.1.1 Release

This procedure verifies the `local synthetic portfolio release`, including the deterministic offline governed DRA candidate import, atomic human verification/promotion, and existing durable-worker mixed PlanningRun closure. It does not deploy Night Voyager, call a live provider, connect live DRA to `/demo`, or validate production behavior.

## 1. Verify merged-main identity

```bash
git fetch origin --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git describe --tags --exact-match HEAD
```

Expected after publication: a clean `main`, identical `HEAD` and `origin/main`, and exact tag `v0.1.1`.

## 2. Verify the annotated tag

```bash
git cat-file -t v0.1.1
git rev-parse v0.1.1^{tag}
git rev-parse v0.1.1^{commit}
```

Expected: object type `tag`; the peeled commit equals the verified release commit. Never move the tag after publication.

## 3. Verify the release gates

Run these commands from the clean reviewed release tree:

```bash
make doctor MODE=dev
uv lock --check
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

Expected: every command exits successfully, the final Compose listing is empty, and the release verifier confirms the current `v0.1.1` identity plus immutable `v0.1.0` historical documents. Live provider proof is intentionally excluded.

## 4. Verify the public source archive

```bash
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.1.tar.gz"
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.1.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
tar -xzf "$archive" -C "$tmp_dir"
cd "$tmp_dir/night-voyager-0.1.1"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all proof commands pass; the final Compose listing is empty. Use the extracted source archive, not the development `.venv`, `node_modules`, retained demo volume, or a custom wheel.

## 5. Failure handling

If merged-main, hosted checks, tag identity, archive identity, governed DRA gates, browser flow, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not force-move `v0.1.1`, replace the archive, bypass the `main` ruleset, run an unauthorized live provider proof, or describe a failed gate as successful.
