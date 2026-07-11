# AMD Return Runbook

## Decision Boundary

Offline evidence is complete for the proof-carrying deterministic+Fireworks runtime. It achieved 100% accuracy on the 80-row final shadow holdout while reducing replayed Fireworks tokens from 2,676 to 1,145. All 40 local releases carried mechanically validated evidence. This is not permission to submit: the local E2B policy is disabled and Docker was not available on the development Mac.

Do not regenerate the sealed shadow holdout. Verify its hashes through `configs/championship-shadow-policy-v1.json` and rerun only the checks explicitly marked below.

## Preflight

```bash
cd ~/track1-token-router
python3 scripts/offline_shadow_championship.py --check
python3 -m unittest tests.test_shadow_championship tests.test_docker_resource_gate -v
python3 scripts/verify_amd_return_manifest.py source --write-checksums
```

Create a complete secret-free snapshot on the Mac. `git ls-files` includes tracked and
untracked project files while respecting `.gitignore`, so local keys, generated reports
and model weights stay out of the archive.

```bash
git ls-files --cached --others --exclude-standard -z \
  | tar --null -T - -czf /tmp/track1-amd-return.tgz
shasum -a 256 /tmp/track1-amd-return.tgz > /tmp/track1-amd-return.tgz.sha256
rsync --partial --append-verify -av /tmp/track1-amd-return.tgz USER@AMD_HOST:~/track1-token-router/
rsync --partial --append-verify -av /tmp/track1-amd-return.tgz.sha256 USER@AMD_HOST:~/track1-token-router/
```

If the pod has no SSH endpoint, upload those same two files through JupyterLab and
compare the archive SHA-256 before extracting. After extraction, rerun the source
verification command; any mismatch is a hard stop.

## Must Rerun On AMD

1. Capture ROCm, GPU, kernel, Python, PyTorch and available-memory versions in `reports/amd-return/environment.json`.
2. Verify the pinned FunctionGemma base revision `39eccb091651513a5dfb56892d3714c1b5b8276c` and Q8 artifact hash from `configs/functiongemma-scale789-q8-runtime.json`.
3. Rebuild or retrieve the text-only Gemma E2B artifact, then record filename, byte size, quantization and SHA-256 in `reports/amd-return/model-artifacts.sha256`. Paths in this file must be relative to the repository root. No E2B artifact without a hash may enter Docker.
4. Measure FunctionGemma plus E2B cold start, p50/p95 latency, peak RSS and two-vCPU throughput. Store results in `reports/amd-return/combined-runtime.json`.
5. Run genuinely fresh inference only. Do not reuse any Sprint 53 holdout for promotion.
6. Run `python3 scripts/verify_amd_return_manifest.py prepare-return` only after every expected artifact exists and parses correctly.
7. Download artifacts with `rsync --partial --append-verify`; verify every hash before using the result locally.

## Docker Gate

Run on CI or another host with Docker Buildx. The AMD notebook is not assumed to expose a Docker daemon.

```bash
docker buildx build --platform linux/amd64 --load -t track1-token-router:amd64 .
scripts/docker_resource_gate.sh track1-token-router:amd64 reports/amd-return/docker-resource-gate.json
docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Size}}' track1-token-router:amd64
docker save track1-token-router:amd64 | gzip -1 > /tmp/track1-token-router-amd64.tar.gz
sha256sum /tmp/track1-token-router-amd64.tar.gz > reports/amd-return/image.sha256
```

The live gate must prove `linux/amd64`, compressed size below 10 GB, 4 GB memory, two CPUs, no network in mock rehearsal, runtime below ten minutes, exit code zero and valid ordered `/output/results.json`.

## Promotion Thresholds

- FunctionGemma schema validity at least 99% and intent accuracy at least 95%.
- Combined local peak RSS no more than 3,584 MB, leaving operating headroom under 4 GB.
- Complete batch runtime no more than 570 seconds, preserving a 30-second evaluator reserve.
- Fresh local precision at least 85% and Wilson lower 95% at least 75%.
- Probability perturbation flip rate strictly below 5%.
- Zero verifier-invalid local releases, zero unauthorized Fireworks models and zero malformed result rows.

Any failed threshold keeps `configs/local-adjudication-policy-v1.json` disabled. Do not lower a threshold after seeing AMD results; create a new policy family and a new untouched confirmation set instead.

## Download

```bash
mkdir -p reports/amd-return
rsync --partial --append-verify -av USER@AMD_HOST:~/track1-token-router/reports/amd-return/ reports/amd-return/
python3 scripts/verify_amd_return_manifest.py verify-return
```

## Completed Offline

- exact official input/output adapter and atomic output writing;
- deadline reserve and one-answer-per-task fallback;
- `ALLOWED_MODELS` authorization and missing-environment fail-closed behavior;
- five replay ablations across all eight categories;
- malformed E2B/Fireworks, timeout and code-sandbox chaos tests;
- static Docker contract and large-weight exclusion;
- hash-pinned deterministic, code and grounded verifiers.

## Release Rule

Release only when both `offline_gate_passed=true` and the live Docker/AMD gates pass. Until then, keep the exact deterministic+Fireworks runtime and do not spend a rate-limited submission attempt.
