# Verify the Night Voyager v0.1.6 Release

This procedure verifies the `local synthetic portfolio release`. It does not deploy Night Voyager, run a provider or credential flow, establish live acceptance, or validate production behavior.

The release identity chain is: reviewed HEAD and hosted checks -> squash tree equality -> exact merge-SHA default-branch CI -> clean-main Gate C -> Git-free Gate D -> annotated tag and GitHub Release -> official public source archive Gate E.

## Gate C — clean merged-main release verification

Run from the clean reviewed release tree after the release pull request is merged:

```bash
set -euo pipefail
export COMPOSE_PROJECT_NAME="night-voyager-v0-1-6-gate-c-$$"
cleanup_compose() {
  gate_status=$?
  trap - EXIT
  teardown_status=0
  docker compose down --volumes --remove-orphans --rmi local \
    || teardown_status=$?
  compose_residue="$(docker compose ps --all --quiet)" || teardown_status=$?
  if [[ -n "$compose_residue" ]]; then
    printf 'Gate C teardown left containers in %s: %s\n' \
      "$COMPOSE_PROJECT_NAME" "$compose_residue" >&2
    teardown_status=1
  fi
  if (( gate_status != 0 )); then
    exit "$gate_status"
  fi
  exit "$teardown_status"
}
trap cleanup_compose EXIT
git fetch origin --tags --prune
git status --short --branch
test -z "$(git status --porcelain)"
test "$(git branch --show-current)" = "main"
expected_commit="$(git rev-parse origin/main)"
test "$(git rev-parse HEAD)" = "$expected_commit"
make doctor MODE=dev
uv lock --check
uv run pytest -q tests/architecture/test_v0_1_6_release_contract.py tests/architecture/test_documentation_governance.py tests/unit/test_release_surface.py
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
uv run python scripts/verify_release.py --tree-mode release
git diff --check
```

Expected: clean `main`, identical `HEAD` and `origin/main`, successful verifier/proof/normal Compose checks, and an empty final Compose state.

## Gate D — Git-free prepublication archive and publication identity

Before publication, rehearse the exact reviewed commit through a Git-free prepublication archive:

```bash
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
expected_commit="$(git -C "$repo_root" rev-parse HEAD)"
tmp_dir="$(mktemp -d)"
cleanup_temp() {
  gate_status=$?
  trap - EXIT
  cleanup_status=0
  rm -rf -- "$tmp_dir" || cleanup_status=$?
  if (( gate_status != 0 )); then
    exit "$gate_status"
  fi
  exit "$cleanup_status"
}
trap cleanup_temp EXIT
archive="$tmp_dir/night-voyager-v0.1.6-prepublication.tar.gz"
git -C "$repo_root" archive \
  --format=tar.gz \
  --prefix=night-voyager-0.1.6/ \
  --output "$archive" \
  "$expected_commit"
python "$repo_root/scripts/validate_release_archive.py" "$archive" \
  --expected-root night-voyager-0.1.6
tar -xzf "$archive" -C "$tmp_dir"
mkdir "$tmp_dir/extracted"
mv "$tmp_dir/night-voyager-0.1.6" "$tmp_dir/extracted/"
test ! -e "$tmp_dir/extracted/night-voyager-0.1.6/.git"
(
  set -euo pipefail
  cd "$tmp_dir/extracted/night-voyager-0.1.6"
  export COMPOSE_PROJECT_NAME="night-voyager-v0-1-6-gate-d-$$"
  cleanup_compose() {
    gate_status=$?
    trap - EXIT
    teardown_status=0
    docker compose down --volumes --remove-orphans --rmi local \
      || teardown_status=$?
    compose_residue="$(docker compose ps --all --quiet)" || teardown_status=$?
    if [[ -n "$compose_residue" ]]; then
      printf 'Gate D teardown left containers in %s: %s\n' \
        "$COMPOSE_PROJECT_NAME" "$compose_residue" >&2
      teardown_status=1
    fi
    if (( gate_status != 0 )); then
      exit "$gate_status"
    fi
    exit "$teardown_status"
  }
  trap cleanup_compose EXIT
  make doctor
  make proof
  make compose-proof
)
```

Only after independent maintainer review, hosted checks, merge, and the prepublication archive pass may an authorized maintainer create the annotated tag and GitHub Release. Verify the published identity:

```bash
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
tmp_dir="$(mktemp -d)"
cleanup_temp() {
  gate_status=$?
  trap - EXIT
  cleanup_status=0
  rm -rf -- "$tmp_dir" || cleanup_status=$?
  if (( gate_status != 0 )); then
    exit "$gate_status"
  fi
  exit "$cleanup_status"
}
trap cleanup_temp EXIT
git -C "$repo_root" fetch origin --tags --prune
expected_commit="$(git -C "$repo_root" rev-parse origin/main)"
git -C "$repo_root" describe --tags --exact-match "$expected_commit"
git -C "$repo_root" cat-file -t v0.1.6
git -C "$repo_root" rev-parse v0.1.6^{tag}
git -C "$repo_root" rev-parse v0.1.6^{commit}
test "$(git -C "$repo_root" rev-parse origin/main)" = "$expected_commit"
test "$(git -C "$repo_root" rev-parse v0.1.6^{commit})" = "$expected_commit"
tag_message="$(git -C "$repo_root" for-each-ref --format='%(contents)' refs/tags/v0.1.6)"
test "$tag_message" = "Night Voyager v0.1.6"

release_view_json="$tmp_dir/release-view.json"
release_api_json="$tmp_dir/release-api.json"
gh release view v0.1.6 \
  --repo iTao-AI/night-voyager \
  --json name,tagName,targetCommitish,isDraft,isPrerelease,assets,url,publishedAt,body \
  > "$release_view_json"
gh api repos/iTao-AI/night-voyager/releases/tags/v0.1.6 \
  > "$release_api_json"
python - "$repo_root" "$release_view_json" "$release_api_json" <<'PY'
import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
release_view = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
release_api = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
expected_body = (repo_root / "docs/releases/v0.1.6.md").read_bytes()
expected_url = "https://github.com/iTao-AI/night-voyager/releases/tag/v0.1.6"

assert release_view["name"] == release_api["name"] == "Night Voyager v0.1.6"
assert release_view["tagName"] == release_api["tag_name"] == "v0.1.6"
assert release_view["targetCommitish"] == release_api["target_commitish"] == "main"
assert release_view["isDraft"] is False
assert release_api["draft"] is False
assert release_view["isPrerelease"] is False
assert release_api["prerelease"] is False
assert release_view["assets"] == release_api["assets"] == []
assert release_view["url"] == release_api["html_url"] == expected_url
assert release_view["publishedAt"] == release_api["published_at"]
assert isinstance(release_view["publishedAt"], str)
assert release_view["publishedAt"].endswith("Z")
assert release_view["body"].encode("utf-8") == expected_body
assert release_api["body"].encode("utf-8") == expected_body
PY
```

Expected: exact tag `v0.1.6`, object type `tag`, and a peeled commit equal to the verified merged release commit. The GitHub Release is public, non-prerelease, targets `main`, has the exact expected tag, URL, publication timestamp, and byte-identical release-notes body, and has no custom assets. GitHub-generated source archives remain the only release artifacts. Never move the tag after publication. Do not force-move `v0.1.6`.

## Gate E — official public source archive

After the authorized GitHub Release exists, verify the public source archive from a fresh extraction:

```bash
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
tmp_dir="$(mktemp -d)"
archive="$tmp_dir/night-voyager-v0.1.6.tar.gz"
archive_root="$tmp_dir/night-voyager-0.1.6"
cleanup_temp() {
  gate_status=$?
  trap - EXIT
  teardown_status=0
  if [[ -d "$archive_root" ]]; then
    cd "$archive_root" || teardown_status=$?
    if (( teardown_status == 0 )); then
      docker compose down --volumes --remove-orphans --rmi local \
        || teardown_status=$?
      compose_residue="$(docker compose ps --all --quiet)" || teardown_status=$?
      if [[ -n "$compose_residue" ]]; then
        printf 'Gate E teardown left containers in %s: %s\n' \
          "$COMPOSE_PROJECT_NAME" "$compose_residue" >&2
        teardown_status=1
      fi
    fi
  fi
  cleanup_status=0
  rm -rf -- "$tmp_dir" || cleanup_status=$?
  if (( gate_status != 0 )); then
    exit "$gate_status"
  fi
  if (( teardown_status != 0 )); then
    exit "$teardown_status"
  fi
  exit "$cleanup_status"
}
trap cleanup_temp EXIT
curl --fail --location --output "$archive" \
  https://github.com/iTao-AI/night-voyager/archive/refs/tags/v0.1.6.tar.gz
wc -c "$archive"
shasum -a 256 "$archive"
python "$repo_root/scripts/validate_release_archive.py" "$archive" \
  --expected-root night-voyager-0.1.6
tar -xzf "$archive" -C "$tmp_dir"
test ! -e "$tmp_dir/night-voyager-0.1.6/.git"
cd "$tmp_dir/night-voyager-0.1.6"
export COMPOSE_PROJECT_NAME="night-voyager-v0-1-6-gate-e-$$"
make doctor
make proof
make compose-proof
```

Expected: the archive has non-zero bytes and a recorded SHA-256; all fresh public source archive smoke checks pass; final Compose state is empty. Use the extracted source archive, not a development `.venv`, `node_modules`, retained volume, custom wheel, or working tree. The archive is the one official GitHub-generated source archive and has no custom assets.

## Failure handling

If merged-main identity, hosted checks, annotated tag identity, archive identity, release contracts, browser flows, or teardown fails, stop and record the exact evidence. Fix the repository through a normal pull request. Do not bypass the `main` ruleset, run an unauthorized provider proof, replace a public archive, or describe a failed gate as successful.
