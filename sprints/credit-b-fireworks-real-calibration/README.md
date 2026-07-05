# Credit Sprint B - Fireworks Real Audit Calibration

## Tipo

Depende de credito Fireworks.

## Objetivo

Validar o auditor Fireworks real e medir custo/token em tarefas escaladas.

## Gatilho

Comecar apenas quando houver `FIREWORKS_API_KEY` com credito disponivel.

## Checklist

- [ ] Configurar `FIREWORKS_API_KEY`.
- [ ] Escolher `FIREWORKS_MODEL`.
- [ ] Rodar chamadas smoke.
- [ ] Medir prompt/completion/total tokens.
- [ ] Testar approve.
- [ ] Testar replace.
- [ ] Comparar modelos Fireworks se houver opcoes.
- [ ] Atualizar politica default.

## Criterios de aceite

- Fireworks real audita M2B.
- Tokens remotos sao registrados corretamente.
- A politica default reflete custo real.

