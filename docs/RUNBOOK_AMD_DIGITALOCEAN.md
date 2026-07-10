# Runbook AMD Developer Cloud + DigitalOcean MI300X

## Objetivo

Subir uma bancada MI300X, expor um endpoint local OpenAI-compatible e validar o router sem redesenhar arquitetura.

Use este runbook apenas quando os creditos AMD Developer Cloud ou DigitalOcean estiverem ativos.

## Decisao operacional

- Comecar com `1x MI300X`.
- Preferir endpoint local em `127.0.0.1` e acessar via SSH tunnel.
- Usar `vLLM` primeiro se a imagem estiver pronta.
- Usar `SGLang` como alternativa se vLLM falhar ou tiver melhor throughput.
- Destruir a VM ao final da sessao para parar custo.

## Preflight local

```bash
git status --short
scripts/offline_release_check.sh
python3 scripts/check_runtime_profiles.py
```

## Provisionamento

1. Entrar pelo fluxo AMD Developer Cloud.
2. Abrir a opcao DigitalOcean se ela for o provedor concreto.
3. Criar GPU Droplet AMD MI300X.
4. Selecionar imagem ROCm ou imagem preconfigurada com vLLM/SGLang quando disponivel.
5. Habilitar SSH key, nao senha.
6. Anotar regiao, tamanho, imagem e horario de criacao em notas locais, nao em git.

## Scratch disk

Use scratch/local disk para pesos e cache, nao o repositorio.

```bash
df -h
mkdir -p /data/models /data/cache /data/logs
```

Se `/data` nao existir, usar o maior volume local disponivel.

## Firewall e rede

Padrao seguro:

- Endpoint do modelo escuta em `127.0.0.1`.
- Acesso externo via SSH tunnel.
- Nao expor porta `8000` ou `30000` publicamente sem firewall.

Tunnel local:

```bash
ssh -L 8000:127.0.0.1:8000 root@<droplet-ip>
```

## Health checks da VM

```bash
scripts/amd_pod_doctor.py
rocm-smi
python3 --version
df -h
free -h
```

Bootstrap padrao do repositorio:

```bash
scripts/bootstrap_amd_pod.sh
```

Se o pod vier com Python 3.10, isso e esperado e suportado pelo projeto.

## Health check do ambiente

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

Esperado:

- ROCm GPU visivel ao PyTorch;
- ambiente base preservado;
- treino segue `docs/FUNCTIONGEMMA_270M_AMD_TRAINING_TUTORIAL.md`.

## Benchmark alvo

```bash
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

## Teardown obrigatorio

Antes de encerrar o trabalho:

1. Salvar apenas logs e reports sem prompts sensiveis.
2. Persistir pesos, locks e relatorios em storage privado.
3. Encerrar a sessao do pod para preservar a cota diaria.
4. Confirmar que nao ha VM, volume pago ou IP reservado ativo.

Regra: VM GPU parada ou esquecida ainda pode custar dinheiro. Destruir quando nao estiver em uso.
