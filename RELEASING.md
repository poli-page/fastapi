# Releasing poli-page-fastapi

The package is published to PyPI as [`poli-page-fastapi`](https://pypi.org/project/poli-page-fastapi/) by the tag-triggered workflow `.github/workflows/release.yml`. No one uploads from a laptop and the repository holds no PyPI token: the workflow authenticates with PyPI Trusted Publishing (OIDC).

## Versions

`poli-page-fastapi` shares its major.minor with the Poli Page API: package `0.13.x` talks to API `0.13`, passes the [API contract](https://github.com/poli-page/api-contract) `v0.13.0`, and requires the `poli-page` SDK of the same minor (`poli-page>=0.13,<0.14`). Patch numbers are free: a fix to the package alone is a patch, whatever the API's or the SDK's patch. A change of the API contract, a new feature, and a raise of the minimum Python or FastAPI version are each a minor. The package may skip minors when it has nothing to ship for one. The Release workflow refuses a version whose major.minor differs from the contract version pinned in `.github/workflows/ci.yml` or from the `poli-page` requirement in `pyproject.toml` and `example-app/pyproject.toml`.

## What the workflow does

On a pushed `vX.Y.Z` tag:

1. **verify** (`contents: read`):
   - the tag version equals `__version__` in `src/poli_page_fastapi/_version.py`;
   - `CHANGELOG.md` has a `## [X.Y.Z]` section;
   - `scripts/check-release-versions.sh`: the API contract commit pinned in `ci.yml` (and the same one in `release.yml`) must carry a stable tag `vX.Y.Z` of the version's major.minor (the `# vX.Y.Z` comment next to the pin is not trusted), and `poli-page` must be required as `>=X.Y,<X.(Y+1)` of that major.minor. The error names both versions;
   - lint (`ruff check`), format (`ruff format --check`), type check (`mypy`), unit tests, and the example app's contract tests, against the pinned API contract (`POLI_CONTRACT`);
   - builds the wheel and sdist, runs `twine check --strict`, and fails if the package holds anything but the library (`src/poli_page_fastapi/`, README, CHANGELOG, LICENSE, `pyproject.toml`): no tests, no example app.
2. **publish** (environment `pypi-publish`, `id-token: write`): uploads the verified wheel and sdist to PyPI with `pypa/gh-action-pypi-publish`, with PEP 740 attestations.
3. **github-release** (`contents: write`): creates the GitHub Release for the tag with the CHANGELOG section as notes and the wheel and sdist attached.

A manual run (**Actions → Release → Run workflow**) runs the same verify job and publishes to TestPyPI only, to rehearse a release. PyPI uploads are immutable: a version can never be uploaded twice, even after it is deleted.

## One-time setup (before the first release)

The name `poli-page-fastapi` is free on PyPI and on TestPyPI (checked 2026-11-04: `https://pypi.org/pypi/poli-page-fastapi/json` answers 404).

1. On pypi.org, signed in to the account that will own the project: **Your account → Publishing → Add a new pending publisher → GitHub**, with:
   - PyPI Project Name: `poli-page-fastapi`
   - Owner: `poli-page`
   - Repository name: `fastapi`
   - Workflow name: `release.yml`
   - Environment name: `pypi-publish`

   The first successful run creates the project and turns the pending publisher into a regular one.
2. Optional, for rehearsals: the same pending publisher on test.pypi.org (a separate account).
3. In GitHub, **poli-page/fastapi → Settings → Environments → New environment** `pypi-publish`, with **Required reviewers** set (the run then waits for approval before uploading) and **Deployment branches and tags** limited to tags matching `v*.*.*` plus the `main` branch (the manual TestPyPI rehearsal runs from `main`).
4. After the first release, on pypi.org: add the other maintainers to the project (**Manage → Collaborators**).

No repository secret is needed.

## Per release

1. Bump `__version__` in `src/poli_page_fastapi/_version.py` and the version shown in `example-app/main.py` (dashboard header and footer).
2. In `CHANGELOG.md`, move the `[Unreleased]` entries under `## [X.Y.Z] - YYYY-MM-DD`, leave an empty `## [Unreleased]` above it, and update the compare links at the bottom.
   - For a new minor `X.Y`: require `poli-page>=X.Y,<X.(Y+1)` in `pyproject.toml` and `example-app/pyproject.toml` and refresh both lock files (`uv lock --upgrade-package poli-page`, at the root and in `example-app/`), pin the API contract's `vX.Y.0` commit in `.github/workflows/ci.yml` and `.github/workflows/release.yml`, update the compatibility table in `README.md`, and check it all with `./scripts/check-release-versions.sh X.Y.Z` (it needs Python 3.11+ and network access to list the contract's tags).
3. Commit (`chore: release X.Y.Z`) through a pull request to `main`, and wait for CI to be green.
4. Optional: rehearse with a manual run of the Release workflow (TestPyPI).
5. Tag the merge commit and push the tag:

   ```bash
   git switch main && git pull
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

6. Approve the `pypi-publish` deployment when the run asks for it. The GitHub Release appears when the upload succeeds.

A tag whose version does not match `_version.py`, a version with no CHANGELOG section, or a major.minor that is not the pinned contract's or the required SDK's fails the verify job before anything is published. Delete the tag (`git push origin :refs/tags/vX.Y.Z`), fix, and tag again.
