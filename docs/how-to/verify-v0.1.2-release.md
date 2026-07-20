# Verify the Night Voyager v0.1.2 Release

This procedure verifies the `local synthetic portfolio release`, including Governed Collaboration Core v1, versioned Skill governance/runtime pins, the primary advisor-to-family `/demo`, and the secondary task-free `/demo/collaboration` walkthrough with its read-only Planning Skill inspector. It does not deploy Night Voyager, call a live provider, connect live DRA/MKE product paths, or validate production behavior.

## 1. Verify merged-main identity

```bash
git fetch origin --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git describe --tags --exact-match HEAD
```

Expected after publication: a clean `main`, identical `HEAD` and `origin/main`, and exact tag `v0.1.2`.

## 2. Verify the annotated tag

```bash
git cat-file -t v0.1.2
git rev-parse v0.1.2^{tag}
git rev-parse v0.1.2^{commit}
```

Expected: object type `tag`; the peeled commit equals the verified release commit. Never move the tag after publication.

## 3. Verify the release gates

Run these commands from the clean reviewed release tree:

```bash
uv lock --check
make doctor MODE=dev
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
uv run ruff check .
uv run pyright
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
git diff --check
```

Expected: every command exits successfully, the final Compose listing is empty, and the release verifier confirms current `v0.1.2` identity plus immutable `v0.1.0` and `v0.1.1` historical documents. Live provider proof is intentionally excluded.

## 4. Verify the public source archive

```bash
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.2.tar.gz"
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.2.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
tar -xzf "$archive" -C "$tmp_dir"
cd "$tmp_dir/night-voyager-0.1.2"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all proof commands pass; the final Compose listing is empty. Use the extracted source archive, not the development `.venv`, `node_modules`, retained demo volume, or a custom wheel.

## 5. Failure handling

If merged-main, hosted checks, tag identity, archive identity, collaboration/Skill authority gates, either browser flow, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not force-move `v0.1.2`, replace the archive, bypass the `main` ruleset, run an unauthorized live provider proof, or describe a failed gate as successful.
