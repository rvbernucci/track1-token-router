# Sprint 41 - Domain Correlation Eval Pack

## Tipo

Nao depende de credito.

## Objetivo

Criar um pacote de avaliacao offline para testar se a matriz de correlacao tarefa-modelo esta classificando os dominios certos e excluindo estrategias ruins.

## Tese

A matriz de correlacao so tem valor se for falsificavel. Precisamos de prompts por dominio com expectativa clara de roteamento, nao apenas exemplos soltos.

## Entregaveis

- `evals/fireworks-pareto/domain-correlation.jsonl`.
- Fixture com `input`, `expected_domain`, `expected_tier`, `expected_allowed_pool`, `forbidden_models`.
- Script `scripts/eval_fireworks_pareto.py`.
- Relatorio `reports/generated/fireworks-pareto-correlation-report.md`.
- Testes unitarios para cobertura minima do dataset.

## Checklist

- [ ] Criar 10 prompts por dominio: cheap, medium, strong-code, strong-math, long-context, factual/current, formatting, extraction.
- [ ] Definir `expected_domain` e `expected_tier` para cada prompt.
- [ ] Definir modelos proibidos: embedding, reranker, underqualified, over-expensive quando aplicavel.
- [ ] Implementar script de replay offline usando `select_fireworks_model`.
- [ ] Gerar matriz de confusao dominio esperado vs dominio roteado.
- [ ] Gerar ranking de modelos escolhidos por categoria.
- [ ] Adicionar teste garantindo que o dataset e parseavel.
- [ ] Adicionar teste com taxa minima de match por dominio.

## Metricas

- domain match rate;
- tier match rate;
- forbidden model violations;
- distribuicao de modelos por dominio;
- taxa de underqualification;
- taxa de over-escalation.

## Definition Of Done

- O eval roda sem Fireworks.
- O relatorio mostra onde a matriz esta acertando e errando.
- Nenhum modelo auxiliar vence resposta final.
- Falhas viram tasks concretas de tuning.

## Anti-Escopo

- Nao chamar API real.
- Nao usar LLM como juiz nesta sprint.
- Nao otimizar pesos antes de ter baseline.
