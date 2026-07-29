# Verify the Night Voyager v0.1.4 Release

This procedure verifies the `local synthetic portfolio release`. It does not deploy Night Voyager, run a provider or credential flow, establish live acceptance, or validate production behavior.

## Gate C — clean merged-main release verification

Run from the clean reviewed release tree after the release pull request is merged:

```bash
git fetch origin --tags --prune
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
make doctor MODE=dev
uv lock --check
uv run pytest -q tests/architecture/test_v0_1_4_release_contract.py tests/architecture/test_documentation_governance.py tests/unit/test_release_surface.py
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

Expected: clean `main`, identical `HEAD` and `origin/main`, successful verifier/proof/normal Compose checks, and an empty final Compose state.

## Gate D — Git-free prepublication archive and publication identity

Before publication, rehearse the exact reviewed commit through a Git-free prepublication archive:

```bash
tmp_dir="$(mktemp -d)"
git archive --format=tar.gz --output "$tmp_dir/night-voyager-v0.1.4-prepublication.tar.gz" HEAD
mkdir "$tmp_dir/extracted"
tar -xzf "$tmp_dir/night-voyager-v0.1.4-prepublication.tar.gz" -C "$tmp_dir/extracted"
test ! -e "$tmp_dir/extracted/.git"
cd "$tmp_dir/extracted"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Only after Career authority review, hosted checks, merge, and the prepublication archive pass may an authorized maintainer create the annotated tag and GitHub Release. Verify the published identity:

```bash
git fetch origin --tags --prune
git describe --tags --exact-match HEAD
git cat-file -t v0.1.4
git rev-parse v0.1.4^{tag}
git rev-parse v0.1.4^{commit}
```

Expected: exact tag `v0.1.4`, object type `tag`, and a peeled commit equal to the verified merged release commit. Never move the tag after publication. Do not force-move `v0.1.4`.

## Gate E — official public source archive

After the authorized GitHub Release exists, verify the public source archive from a fresh extraction:

```bash
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.4.tar.gz"
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.4.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
tar -xzf "$archive" -C "$tmp_dir"
cd "$tmp_dir/night-voyager-0.1.4"
make doctor
make proof
make compose-proof
make down
docker compose ps --all
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all fresh public source archive smoke checks pass; final Compose state is empty. Use the extracted source archive, not a development `.venv`, `node_modules`, retained volume, custom wheel, or working tree.

## Failure handling

If merged-main identity, hosted checks, annotated tag identity, archive identity, release contracts, browser flows, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not bypass the `main` ruleset, run an unauthorized provider proof, replace a public archive, or describe a failed gate as successful.
