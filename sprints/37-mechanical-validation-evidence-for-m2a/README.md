# Sprint 37 - Mechanical Validation Evidence For M2A

## Tipo

Nao depende de credito.

## Objetivo

Construir um motor de validacao mecanica que analisa a resposta candidata do M1 antes do M2A decidir.

O motor deve produzir evidencias deterministicas sobre formato, matematica simples, transformacoes, literal echo, JSON, resposta vazia, excesso de texto, prompt injection e conhecimento instavel. Essas evidencias entram no prompt do M2A como um laudo curto.

## Tese

O M2A nao deve ser calculadora, parser de JSON ou regex humano.

O codigo deve provar o que for provavel mecanicamente. O M2A deve julgar o que sobrar: incerteza, ambiguidade, factualidade, risco silencioso e custo esperado de escalacao.

## Por que importa

Sem validacao mecanica, o M2A pode:

- aprovar resposta bonita e errada;
- escalar tarefa que o codigo poderia provar correta;
- gastar M2B/Fireworks por erro de formato reparavel;
- confundir fluencia com verificabilidade;
- perder pontos por formato estrito simples.

Com validacao mecanica, a cascata ganha um terceiro tipo de inteligencia:

- solver deterministico antes do modelo;
- geracao local com M1;
- evidencia mecanica entre M1 e M2A;
- julgamento calibrado com M2A;
- reparo local ou auditoria remota quando necessario.

## Arquitetura alvo

```text
TaskEnvelope
  -> guardrails / deterministic solvers
  -> M1 candidate
  -> MechanicalValidationEngine
  -> M2A receives task + candidate + mechanical evidence
  -> approve, escalate to M2B, or remote audit policy
```

## Novo modulo alvo

`router/orchestration/mechanical_validation.py`

## Contratos alvo

```python
@dataclass(frozen=True)
class MechanicalCheck:
    name: str
    status: str
    reason: str
    expected: str = ""
    observed: str = ""
    confidence: str = "medium"


@dataclass(frozen=True)
class MechanicalValidationReport:
    overall: str
    recommendation: str
    checks: list[MechanicalCheck]
    evidence_summary: str
```

## Estados alvo

`MechanicalCheck.status`:

- `pass`: o check provou que aquele criterio foi satisfeito;
- `fail`: o check provou uma violacao;
- `not_applicable`: o check nao se aplica;
- `unverifiable`: o check se aplica, mas nao pode ser provado mecanicamente.

`MechanicalValidationReport.overall`:

- `proven_valid`: todos os criterios relevantes foram provados;
- `proven_invalid`: pelo menos uma violacao relevante foi provada;
- `mixed`: ha sinais bons e ruins;
- `unverifiable`: nao ha prova mecanica suficiente.

`MechanicalValidationReport.recommendation`:

- `approve_candidate`: evidencia mecanica forte para aprovar;
- `escalate_repair`: evidencia mecanica de erro ou formato quebrado;
- `escalate_uncertain`: nao verificavel mecanicamente;
- `remote_audit`: conhecimento atual, fato raro ou risco que codigo local nao valida.

## Checks mecanicos v1

### Formato final

- JSON valido quando a tarefa pede JSON.
- JSON compacto quando a tarefa pede `compact JSON`.
- Numero puro quando a tarefa pede `return only the number`.
- Literal echo quando a tarefa pede `return exactly`.
- Uppercase/lowercase quando a tarefa pede transformacao de caixa.
- Sem markdown fence em formato estrito.
- Sem texto extra quando a tarefa pede `nothing else`.

### Conteudo mecanico

- Aritmetica simples parseavel.
- Comparacao numerica entre dois numeros.
- Contagem de caracteres em string entre aspas.
- Contagem de palavras em string entre aspas.
- Primeiro/ultimo item de lista simples.
- Normalizacao/trim de whitespace.

### Saude da resposta

- Resposta vazia.
- Resposta curta demais fora de caso numerico/literal.
- Resposta longa demais para tarefa simples.
- Recusa indevida quando a tarefa era segura.
- Resposta generica sem responder o pedido.

### Risco nao verificavel

- `current`, `latest`, `today`, `now`, `price`, `CEO`, `schedule`, `rules`, `version`.
- Pedido factual especifico sem fonte no prompt.
- Prompt injection ou pedido de revelar prompt.
- Tarefa legal, medica, financeira, seguranca ou codigo com edge cases.

### Categorias oficiais Track 1

O Participant Guide confirma oito categorias. O motor mecanico deve ter pelo menos um sinal ou fixture para cada uma:

- factual knowledge: detectar fato externo ou atual como nao verificavel;
- mathematical reasoning: provar casos simples e marcar multi-step como risco;
- sentiment classification: validar labels permitidos e justificativa quando exigida;
- text summarisation: validar limite de frase/palavras quando pedido;
- named entity recognition: validar JSON/lista de entidades quando formato for explicito;
- code debugging: validar presenca de bug/fix quando formato for explicito, sem executar codigo inseguro;
- logical / deductive reasoning: marcar puzzles multi-condicao como nao verificaveis mecanicamente v1;
- code generation: validar formato/assinatura quando parseavel, sem prometer corretude sem teste.

## Formato do pacote para M2A

O M2A deve receber um bloco novo:

```text
<mechanical_validation evidence_kind="deterministic_checks">
overall: proven_invalid
recommendation: escalate_repair
evidence_summary: strict number format failed; observed extra prose
checks:
- final_number_format: fail | expected number-only | observed prose+number
- stale_knowledge: not_applicable
- prompt_injection: not_applicable
</mechanical_validation>
```

Regra:

- se `proven_valid`, M2A pode aprovar com mais seguranca;
- se `proven_invalid`, M2A deve escalar ou pedir reparo;
- se `unverifiable`, M2A decide por rubrica;
- se `remote_audit`, politica/budget deve tratar como candidato remoto.

## Checklist

- [ ] Criar `router/orchestration/mechanical_validation.py`.
- [ ] Definir `MechanicalCheck`.
- [ ] Definir `MechanicalValidationReport`.
- [ ] Implementar inferencia de checks a partir de `TaskEnvelope` + candidate.
- [ ] Reusar `infer_expected_format`, `extract_literal_echo` e validadores existentes.
- [ ] Validar JSON valido/compacto.
- [ ] Validar numero puro.
- [ ] Validar literal echo.
- [ ] Validar uppercase/lowercase.
- [ ] Validar markdown fence em formato estrito.
- [ ] Validar aritmetica simples e comparacao numerica quando parseavel.
- [ ] Detectar conhecimento instavel como `remote_audit`.
- [ ] Detectar prompt injection como risco.
- [ ] Gerar `evidence_summary` curto e estavel.
- [ ] Adicionar bloco de evidencia ao `build_m2a_messages`.
- [ ] Atualizar prompt M2A v2 para obedecer evidencia mecanica.
- [ ] Registrar evidencia em metadata/logs sem vazar prompt bruto longo.
- [ ] Adicionar testes unitarios de cada check.
- [ ] Adicionar testes de integracao M1 -> mechanical evidence -> M2A.
- [ ] Adicionar fixture de caos onde M1 erra formato e o motor prova a falha.
- [ ] Integrar no `offline_release_check.sh`.

## Criterios de aceite

- Motor mecanico roda sem modelo, sem rede e sem credito.
- Checks deterministicos nunca inventam resposta quando nao conseguem provar.
- Relatorio diferencia `fail`, `unverifiable` e `not_applicable`.
- M2A recebe evidencia mecanica em envelope separado.
- Erros de formato simples sao detectados antes de Fireworks.
- Conhecimento atual vira recomendacao de auditoria remota.
- Testes cobrem casos positivos, negativos e nao verificaveis.
- Release check offline continua verde.

## Metricas

- `mechanical_checks_total`.
- `mechanical_pass_count`.
- `mechanical_fail_count`.
- `mechanical_unverifiable_count`.
- `mechanical_recommendation`.
- `m2a_approval_rate_after_mechanical_evidence`.
- `strict_format_failure_caught_rate`.
- `remote_audit_recommended_count`.

## Experimentos

- M2A sem evidencia mecanica vs M2A com evidencia mecanica.
- Aprovar automaticamente `proven_valid` vs ainda pedir M2A.
- Usar evidencia mecanica apenas no prompt vs tambem na policy engine.
- Reparar formato mecanicamente antes de M2A vs pedir M2B.

## Riscos

- Regex agressivo demais gerar falso positivo.
- Motor mecanico tentar resolver coisa probabilistica.
- Duplicar logica entre solvers, final validator e mechanical engine.
- Envelope de evidencia ficar grande demais e distrair M2A.
- Uma recomendacao mecanica virar autoridade absoluta quando deveria ser evidencial.

## Decisoes

- O motor mecanico nao substitui M2A.
- O motor mecanico nao chama modelo.
- O motor mecanico nao deve navegar internet.
- O motor mecanico nao valida fatos externos.
- O motor mecanico so prova o que consegue demonstrar por codigo.

## Definition of Done

- `MechanicalValidationEngine` implementado.
- M2A recebe o laudo mecanico.
- Testes unitarios e integrados passam.
- Release check offline passa.
- Documentacao explica quando confiar no codigo e quando escalar para julgamento.

## Comandos esperados

```bash
python3 -m unittest tests.test_mechanical_validation
python3 -m unittest tests.test_local_cascade tests.test_competition_mode
scripts/offline_release_check.sh
```
