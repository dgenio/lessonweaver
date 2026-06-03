# Release process

This document describes how to publish a new lessonweaver release to PyPI. The
package is published automatically by the
[`publish.yml`](../.github/workflows/publish.yml) workflow when a GitHub Release
is published, using PyPI Trusted Publishing (OIDC) — no API tokens are stored.

## Prerequisites

- Maintainer access to the repository and the PyPI project.
- A clean working tree on an up-to-date `main`.
- Dev tooling installed: `pip install -e ".[dev]"`.

## Checklist

1. **Pick the version.** Follow [SemVer](https://semver.org/). Update `version`
   in `pyproject.toml`.
2. **Update the changelog.** Move the `[Unreleased]` notes in
   [`CHANGELOG.md`](../CHANGELOG.md) into a new version section with today's
   date. For the first tagged release, uncomment the comparison/release link
   template at the bottom of the changelog and fill it in; on later releases,
   update those links.
3. **Run the full local check** (the same checks CI runs):
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   mypy src/lessonweaver/
   pytest
   ```
4. **Build the distribution and verify it.** Clean `dist/` first so stale
   artifacts from a previous version can't be checked or uploaded:
   ```bash
   rm -rf dist/
   python -m build
   twine check dist/*
   ```
   Confirm the wheel ships the type marker:
   ```bash
   python -c "import zipfile,glob; w=glob.glob('dist/*.whl')[0]; print('lessonweaver/py.typed' in zipfile.ZipFile(w).namelist())"
   ```
   This must print `True`.
5. **(Optional) Smoke-test on TestPyPI:**
   ```bash
   twine upload --repository testpypi dist/*
   python -m pip install --index-url https://test.pypi.org/simple/ lessonweaver
   lessonweaver --help
   ```
6. **Commit and tag** the version bump and changelog on `main`:
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push origin main --tags
   ```
7. **Publish the GitHub Release** for the `vX.Y.Z` tag with the changelog notes.
   Publishing the release triggers `publish.yml`, which builds and uploads to
   PyPI.
8. **Verify the release** is live:
   ```bash
   python -m pip install lessonweaver
   lessonweaver --help
   ```

## Notes

- The first public release also requires the PyPI project name `lessonweaver`
  to be registered and Trusted Publishing to be configured for this repository.
- Do not add runtime dependencies as part of a release. Optional integrations
  belong in `[project.optional-dependencies]`.
