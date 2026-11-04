#!/usr/bin/env bash
# scripts/check-release-versions.sh: a release's major.minor must be the
# pinned API contract's and the required poli-page SDK's.
#
# Usage: scripts/check-release-versions.sh X.Y.Z   (or vX.Y.Z, or a PEP 440
#        prerelease such as 0.13.0rc1)
#
# The package shares its major.minor with the Poli Page API, and integration
# 0.N requires the poli-page SDK 0.N.x. This script:
#   - fails unless pyproject.toml and example-app/pyproject.toml require
#     poli-page as `>=X.Y,<X.(Y+1)` (or `>=X.Y.Z,<X.(Y+1)`) of the release's
#     major.minor;
#   - reads the contract commit pinned in .github/workflows/ci.yml (never its
#     `# vX.Y.Z` comment, never a commented-out line), checks that release.yml
#     pins the same commit, lists the contract repository's tags, and fails
#     unless that commit carries a stable tag vX.Y.Z with the release's
#     major.minor.
# Patch numbers are free.
#
# Run by the Release workflow. It needs Python 3.11+ (tomllib) as `python3`, or
# as $PYTHON. API_CONTRACT_REMOTE overrides the contract repository (to check
# against a local one).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CI_WORKFLOW="$REPO_ROOT/.github/workflows/ci.yml"
RELEASE_WORKFLOW="$REPO_ROOT/.github/workflows/release.yml"
REMOTE="${API_CONTRACT_REMOTE:-https://github.com/poli-page/api-contract.git}"
PYTHON="${PYTHON:-python3}"

fail() { echo "check-release-versions: $1" >&2; exit 1; }

[ "$#" -eq 1 ] || fail "usage: $(basename "$0") X.Y.Z"
version="${1#v}"
# X.Y.Z, then an optional PEP 440 pre-, post- or dev-release suffix.
if ! [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.[0-9]+((a|b|rc)[0-9]+)?(\.post[0-9]+)?(\.dev[0-9]+)?$ ]]; then
    fail "release version '$1' is not X.Y.Z"
fi
release_major="${BASH_REMATCH[1]}"
release_minor_num="${BASH_REMATCH[2]}"
release_minor="$release_major.$release_minor_num"
next_minor="$release_major.$((10#$release_minor_num + 1))"

# The poli-page requirement of a pyproject.toml's [project].dependencies, with
# its whitespace removed; nothing when there is none, an error when there are
# several. The name is compared in its PEP 503 normalized form.
sdk_requirement_of() {
    "$PYTHON" - "$1" <<'EOF'
import re, sys, tomllib

with open(sys.argv[1], "rb") as f:
    deps = tomllib.load(f).get("project", {}).get("dependencies", [])
found = []
for dep in deps:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", dep)
    if m and re.sub(r"[-_.]+", "-", m.group(1)).lower() == "poli-page":
        found.append(re.sub(r"\s+", "", dep[m.end():]))
if len(found) > 1:
    sys.exit(f"{sys.argv[1]} requires poli-page {len(found)} times")
if found:
    print(found[0])
EOF
}

# poli-page: `>=X.Y` or `>=X.Y.Z`, and `<X.(Y+1)` or `<X.(Y+1).0`, in either
# order, with nothing else (no extras, markers or other specifiers).
lower="(>=${release_major}\\.${release_minor_num}(\\.[0-9]+)?)"
upper="(<${release_major}\\.$((10#$release_minor_num + 1))(\\.0)?)"
for manifest in pyproject.toml example-app/pyproject.toml; do
    [ -f "$REPO_ROOT/$manifest" ] || fail "$manifest is missing"
    constraint="$(sdk_requirement_of "$REPO_ROOT/$manifest")" || fail "cannot read the poli-page requirement of $manifest"
    [ -n "$constraint" ] || fail "$manifest does not require poli-page"
    if ! [[ "$constraint" =~ ^($lower,$upper|$upper,$lower)$ ]]; then
        hint="require poli-page >=$release_minor,<$next_minor"
        if [[ "$constraint" =~ \>=([0-9]+)\.([0-9]+) ]] && [ "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}" != "$release_minor" ]; then
            hint="$hint, or release v${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.x"
        fi
        fail "release v$version needs poli-page >=$release_minor,<$next_minor, but $manifest requires poli-page '$constraint': $hint"
    fi
done
echo "poli-page >=$release_minor,<$next_minor is required, matching release v$version"

# The pinned commit of a `uses:` step line; a commented-out line does not count.
pin_of() {
    sed -n 's|^[[:space:]]*-\{0,1\}[[:space:]]*uses:[[:space:]]*poli-page/api-contract@\([0-9a-f]\{40\}\).*|\1|p' "$1" | head -n 1
}

contract_sha="$(pin_of "$CI_WORKFLOW")"
[ -n "$contract_sha" ] || fail "no poli-page/api-contract pin found in .github/workflows/ci.yml"

# The Release workflow runs the contract tests against its own pin: it must be the same one.
release_sha="$(pin_of "$RELEASE_WORKFLOW")"
[ "$release_sha" = "$contract_sha" ] ||
    fail "release.yml pins the API contract ${release_sha:-nowhere}, ci.yml pins $contract_sha: pin the same commit in both"

tags="$(git ls-remote --tags "$REMOTE")" || fail "cannot list the tags of $REMOTE"

# An annotated tag is listed twice: its own object, then `^{}` with the commit
# it points at. A lightweight tag is listed once, with its commit.
stable_tags="$(
    awk -v sha="$contract_sha" '$1 == sha { ref = $2; sub(/^refs\/tags\//, "", ref); sub(/\^\{\}$/, "", ref); print ref }' <<<"$tags" \
        | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -u -V || true
)"
short_sha="${contract_sha:0:8}"
if [ -z "$stable_tags" ]; then
    fail "release v$version needs the API contract v$release_minor.x, but the pinned contract commit $short_sha has no stable vX.Y.Z tag: pin a released contract"
fi

while IFS= read -r tag; do
    if [[ "$tag" =~ ^v([0-9]+)\.([0-9]+)\. ]] && [ "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}" = "$release_minor" ]; then
        echo "API contract $tag ($short_sha) matches release v$version"
        exit 0
    fi
done <<<"$stable_tags"

pinned="$(tr '\n' ' ' <<<"$stable_tags" | sed 's/ $//')"
# The newest of the commit's tags, which may carry two (an unchanged contract).
[[ "$(tail -n 1 <<<"$stable_tags")" =~ ^v([0-9]+)\.([0-9]+)\. ]]
fail "release v$version and the pinned API contract $pinned ($short_sha) differ in major.minor: pin the contract v$release_minor.x, or release v${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.x"
