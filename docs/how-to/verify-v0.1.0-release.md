# Verify the Night Voyager v0.1.0 Release

This procedure verifies the `local synthetic portfolio release`. It does not deploy Night Voyager or validate production behavior.

## 1. Verify merged-main identity

```bash
git fetch origin --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git describe --tags --exact-match HEAD
```

Expected after publication: a clean `main`, identical `HEAD` and `origin/main`, and exact tag `v0.1.0`.

## 2. Verify the annotated tag

```bash
git cat-file -t v0.1.0
git rev-parse v0.1.0^{tag}
git rev-parse v0.1.0^{commit}
```

Expected: object type `tag`; the peeled commit equals the verified release commit. Never move the tag after publication.

## 3. Verify the public source archive

```bash
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.0.tar.gz"
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.0.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
tar -xzf "$archive" -C "$tmp_dir"
cd "$tmp_dir/night-voyager-0.1.0"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all proof commands pass; the final Compose listing is empty. Use the extracted source archive, not the development `.venv`, `node_modules`, retained demo volume, or a custom wheel.

## 4. Failure handling

If merged-main, hosted checks, tag identity, archive identity, browser flow, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not force-move `v0.1.0`, replace the archive, bypass the `main` ruleset, or describe a failed gate as successful.
