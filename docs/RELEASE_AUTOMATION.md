# Release Automation

Sprint 16 adds a tag-only release path for the public repository.

## Tag format

Use one of:

- `v0.1.0`, `v0.2.0`, `v1.0.0`
- `offline-rc-1`, `offline-rc-2`

## Local dry-run

```bash
python3 scripts/generate_release_notes.py \
  --tag offline-dry-run \
  --output reports/generated/release-notes.md
```

## GHCR publishing

The workflow `.github/workflows/release.yml` publishes to:

```text
ghcr.io/<owner>/<repo>:<tag>
```

It runs on tag pushes, can also be started manually with `workflow_dispatch`, and uses the built-in `GITHUB_TOKEN`.

The Docker image is built with Buildx for the required judging architecture:

```text
linux/amd64
```

## Publish an offline RC image

```bash
git tag offline-rc-YYYYMMDD-HHMM
git push origin offline-rc-YYYYMMDD-HHMM
```

After the Release workflow succeeds, the image should be pullable as:

```bash
docker pull ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM
```

If GHCR shows the package as private, make the package public in GitHub Packages before submitting the image URL.

When Docker is unavailable locally, use the submission audit instead:

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM
```

This validates the public registry manifest, `linux/amd64`, and the 10GB compressed image limit.

For final traceability, also verify the OCI labels written by the Release workflow:

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM \
  --expected-revision "$(git rev-list -n 1 offline-rc-YYYYMMDD-HHMM)" \
  --expected-version offline-rc-YYYYMMDD-HHMM
```

The image labels include `org.opencontainers.image.source`, `org.opencontainers.image.revision`, and `org.opencontainers.image.version`.

## Safety rules

- Normal pushes to `main` do not publish an image.
- No AMD, Fireworks or manual registry secret is required.
- The offline release check runs before Docker login/build/push.
- The image is labelled with OCI source, revision and version metadata so GHCR links it back to the public repository and release commit.
