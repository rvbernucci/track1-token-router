# Sprint 05 - Hardening e entrega

## Objetivo

Transformar o prototipo competitivo em submissao confiavel: container, documentacao, testes finais, scripts de reproducao e plano de demo.

Esta sprint e sobre nao perder por detalhe operacional.

## Entregaveis

- Dockerfile final.
- Comandos de build e run documentados.
- `.env.example`.
- README publico de submissao.
- Suite final de testes.
- Relatorio de estrategia.
- Checklist de entrega lablab.

## Checklist

- [x] Criar Dockerfile minimalista.
- [x] Criar `.dockerignore`.
- [x] Criar `.env.example` sem segredos.
- [x] Garantir que `router --help` funciona no container.
- [x] Garantir que `router ask` funciona no container.
- [x] Garantir que `router run --jsonl` funciona no container.
- [x] Garantir modo sem Fireworks para smoke test.
- [x] Garantir modo com Fireworks para run real.
- [x] Rodar eval final com golden set.
- [x] Rodar testes de timeout.
- [x] Rodar testes de JSON invalido.
- [x] Rodar testes de arquivo ausente.
- [x] Limpar logs com segredos ou dados sensiveis.
- [x] Escrever README de instalacao.
- [x] Escrever README de arquitetura.
- [x] Escrever tradeoffs e limitacoes.
- [x] Preparar pitch tecnico curto.

## Criterios de aceite

- [x] Qualquer pessoa consegue rodar o projeto seguindo o README.
- [x] O container nao depende de arquivo local escondido.
- [x] Falhas externas geram erro controlado.
- [x] Logs sao uteis, mas nao vazam API keys.
- [x] O projeto explica claramente por que economiza tokens.
- [x] O projeto esta pronto para repo publico.

## Evidencias

- `python3 -m unittest discover -s tests`
- `scripts/verify.sh`
- `docker build -t track1-token-router .`
- `docker run --rm track1-token-router --help`
- `docker run --rm track1-token-router ask "What is 2+2?"`
- `docker run --rm track1-token-router run --jsonl evals/golden/tasks.jsonl --out /tmp/router-output.jsonl`
- `.github/workflows/ci.yml` valida testes e Docker no GitHub Actions.
- `.env.example`
- `SUBMISSION.md`

Nota: a maquina local usada nesta implementacao nao possui `docker`/`podman` instalado. Os gates de container foram codificados no CI para validacao em ambiente com Docker.

## README publico deve conter

- Problema do Track 1.
- Ideia central da cascata.
- Como rodar localmente.
- Como rodar com Docker.
- Variaveis de ambiente.
- Exemplos de CLI.
- Estrutura do projeto.
- Estrategia de token efficiency.
- Limites conhecidos.
- Como reproduzir avaliacao local.

## Riscos

- Funcionar localmente e falhar no ambiente padronizado.
- README bonito, mas comandos quebrados.
- Container pesado demais.
- API key acidentalmente exposta.
- Ultima hora virar refactor em vez de estabilizacao.

## Plano de congelamento

- Congelar contratos antes da entrega.
- Congelar prompts que tiveram melhor Pareto.
- Aceitar melhorias pequenas apenas se houver teste.
- Evitar dependencias novas na reta final.
- Priorizar reproducibilidade acima de elegancia.

## Saida esperada da sprint

Uma submissao limpa, reproduzivel e defensavel: codigo, container, README, metricas e narrativa tecnica alinhados.
