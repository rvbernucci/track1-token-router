# Sprint 23 - Official Input Fuzz Pack

## Tipo

Nao depende de credito.

## Objetivo

Criar um pacote de fuzzing para simular formatos de input/output que podem aparecer no evaluator oficial, incluindo texto livre, JSON, JSONL, arquivos, payloads grandes, unicode, schemas rigidos e casos quebrados.

## Por que importa

O maior risco do kickoff nao e so modelo. E contrato. Se o input oficial vier diferente do que esperamos, o runner precisa falhar de forma controlada ou adaptar rapidamente.

## Entregaveis

- `evals/fuzz/tasks.jsonl`.
- `evals/fuzz/expected.jsonl`.
- Fixtures de arquivos anexos.
- Script `scripts/generate_fuzz_eval.py`.
- Script `scripts/run_fuzz_eval.py`.
- Relatorio `reports/generated/fuzz-report.md`.
- Testes de adapters e CLI contra payloads adversariais.

## Checklist

- [x] Criar casos de texto vazio.
- [x] Criar casos com whitespace extremo.
- [x] Criar casos com unicode e acentos.
- [x] Criar casos multi-linha.
- [x] Criar casos JSON com campos alternativos.
- [x] Criar casos JSONL com linhas invalidas controladas.
- [x] Criar casos com arquivo `.txt`.
- [x] Criar casos com arquivo `.json`.
- [x] Criar casos com payload grande.
- [x] Criar casos de resposta `number only`.
- [x] Criar casos de resposta JSON compacta.
- [x] Criar casos de literal echo.
- [x] Criar casos com markdown proibido.
- [x] Validar que erros controlados vao para `stderr`.
- [x] Validar que `stdout` nao recebe debug.
- [x] Integrar fuzz report ao battle drill.

## Criterios de aceite

- O pacote roda sem creditos.
- O runner nao quebra com formatos estranhos.
- O relatorio mostra classes de input e taxa de sucesso.
- Falhas de parse sao controladas e testadas.

## Saida esperada

Menos surpresa no kickoff e maior chance de adaptar o adapter oficial em minutos, nao horas.

## Decisao

O fuzz pack deve testar contrato e robustez, nao qualidade semantica profunda. Ele existe para proteger o runner contra formato inesperado.

## Evidencia de fechamento

- `python3 scripts/generate_fuzz_eval.py --check`: dataset e fixtures validos.
- `python3 scripts/run_fuzz_eval.py --check`: `contract_success=true`, 16 tasks, 15 classes e traces completos.
- `python3 -m unittest tests.test_fuzz_pack tests.test_battle_drill`: fuzz pack, stderr controlado, stdout limpo e battle drill integrados.
