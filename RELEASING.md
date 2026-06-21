# Releasing

This package publishes to PyPI through GitHub Actions. Publishing uses PyPI
Trusted Publishing (OIDC), so there is no API token to store or rotate. The
`release` workflow runs on any pushed tag that matches `v*.*.*`.

## One-time setup

Do this once, before the first release.

### 1. Reserve the project name on PyPI

The project name `demografix` must exist on PyPI, or be claimable by the
account that registers the Trusted Publisher. Confirm the name is available at
https://pypi.org/project/demografix/ before going further.

### 2. Register the Trusted Publisher on PyPI

In the PyPI project settings, under "Publishing", add a new GitHub trusted
publisher with these exact values:

- Owner: `DemografixGenderize`
- Repository: `demografix-python`
- Workflow name: `release.yml`
- Environment: `release`

If the project does not exist on PyPI yet, register the publisher as a
"pending" publisher instead. PyPI creates the project on the first successful
upload.

### 3. Create the `release` environment in GitHub

In the repository settings, under "Environments", create an environment named
`release`. The publish job references this environment. Add required reviewers
or branch restrictions here if you want a manual gate before any upload.

No secrets are required. Trusted Publishing exchanges a short-lived OIDC token
for the upload credential at publish time. Do not add a `PYPI_API_TOKEN` or any
password.

## Cutting a release

1. Bump `version` in `pyproject.toml` to the new `X.Y.Z`.
2. Commit the bump:

   ```
   git commit -am "Release vX.Y.Z"
   ```

3. Tag the commit. The tag must match the manifest version, with a `v` prefix:

   ```
   git tag vX.Y.Z
   ```

4. Push the commit and the tag:

   ```
   git push origin main
   git push origin vX.Y.Z
   ```

Pushing the tag starts the `release` workflow. It verifies the tag matches the
`pyproject.toml` version, builds the sdist and wheel, publishes to PyPI, and
creates a GitHub Release with the built artifacts attached.

## If a release fails

- Tag/version mismatch: the build job stops before publishing. Delete the tag
  (`git tag -d vX.Y.Z` and `git push origin :vX.Y.Z`), fix the version, and tag
  again.
- PyPI rejects the upload because the version already exists: bump to a new
  version and tag again. PyPI does not allow re-uploading an existing version.
