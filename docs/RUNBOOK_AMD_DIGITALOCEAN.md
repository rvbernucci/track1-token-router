# Runbook AMD Developer Cloud + DigitalOcean MI300X

## Objective

Spin up an MI300X workbench, expose a local OpenAI-compatible endpoint, and validate the router without redesigning the architecture.

Use this runbook only when AMD Developer Cloud or DigitalOcean credits are active.

## Operational Decision

- Start with `1x MI300X`.
- Prefer local endpoint on `127.0.0.1` and access via SSH tunnel.
- Use `vLLM` first if the image is ready.
- Use `SGLang` as an alternative if vLLM fails or has better throughput.
- Destroy the VM at the end of the session to stop costs.

## Local Preflight

```bash
git status --short
scripts/offline_release_check.sh
python3 scripts/check_runtime_profiles.py
```

## Provisioning

1. Enter via the AMD Developer Cloud flow.
2. Open the DigitalOcean option if it is the concrete provider.
3. Create an AMD MI300X GPU Droplet.
4. Select a ROCm image or a preconfigured image with vLLM/SGLang when available.
5. Enable SSH key, not a password.
6. Note the region, size, image, and creation time in local notes, not in git.

## Scratch disk

Use scratch/local disk for weights and cache, not the repository.

```bash
df -h
mkdir -p /data/models /data/cache /data/logs
```

If `/data` does not exist, use the largest local volume available.

## Firewall and Network

Secure default:

- Model endpoint listens on `127.0.0.1`.
- External access via SSH tunnel.
- Do not expose port `8000` or `30000` publicly without a firewall.

Local tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 root@<droplet-ip>
```

## VM Health Checks

```bash
scripts/amd_pod_doctor.py
rocm-smi
python3 --version
df -h
free -h
```

Standard repository bootstrap:

```bash
scripts/bootstrap_amd_pod.sh
```

If the pod comes with Python 3.10, this is expected and supported by the project.

## Environment Health Check

```bash
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

## Training setup

```bash
cp runtime-profiles/functiongemma-router.env.example .env.functiongemma
set -a
. ./.env.functiongemma
set +a
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

Expected:

- ROCm GPU visible to PyTorch;
- base environment preserved;
- training follows `docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md`.

## Target Benchmark

```bash
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

## Mandatory Teardown

Before ending the work:

1. Save only logs and reports without sensitive prompts.
2. Persist weights, locks, and reports in private storage.
3. End the pod session to preserve the daily quota.
4. Confirm that there is no active VM, paid volume, or reserved IP.

Rule: A stopped or forgotten GPU VM can still cost money. Destroy it when not in use.
