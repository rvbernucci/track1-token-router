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

- [ ] Criar Dockerfile minimalista.
- [ ] Criar `.dockerignore`.
- [ ] Criar `.env.example` sem segredos.
- [ ] Garantir que `router --help` funciona no container.
- [ ] Garantir que `router ask` funciona no container.
- [ ] Garantir que `router run --jsonl` funciona no container.
- [ ] Garantir modo sem Fireworks para smoke test.
- [ ] Garantir modo com Fireworks para run real.
- [ ] Rodar eval final com golden set.
- [ ] Rodar testes de timeout.
- [ ] Rodar testes de JSON invalido.
- [ ] Rodar testes de arquivo ausente.
- [ ] Limpar logs com segredos ou dados sensiveis.
- [ ] Escrever README de instalacao.
- [ ] Escrever README de arquitetura.
- [ ] Escrever tradeoffs e limitacoes.
- [ ] Preparar pitch tecnico curto.

## Criterios de aceite

- Qualquer pessoa consegue rodar o projeto seguindo o README.
- O container nao depende de arquivo local escondido.
- Falhas externas geram erro controlado.
- Logs sao uteis, mas nao vazam API keys.
- O projeto explica claramente por que economiza tokens.
- O projeto esta pronto para repo publico.

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

