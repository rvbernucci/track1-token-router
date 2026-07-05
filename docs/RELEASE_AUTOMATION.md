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

It only runs on tag pushes and uses the built-in `GITHUB_TOKEN`.

## Safety rules

- Normal pushes to `main` do not publish an image.
- No AMD, Fireworks or manual registry secret is required.
- The offline release check runs before Docker login/build/push.
