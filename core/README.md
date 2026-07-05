# Core

Responsavel pela logica competitiva do router.

## O que mora aqui

- `TaskEnvelope`: contrato generico de entrada.
- `AnswerResult`: contrato generico de saida.
- `CascadeRunner`: orquestrador da cascata.
- `LocalModelClient`: cliente para modelo local OpenAI-compatible.
- `FireworksClient`: cliente remoto Fireworks.
- `M1Generator`: gera candidato livre, sem reasoning.
- `M2AVerifier`: valida candidato em JSON pequeno, com reasoning.
- `M2BGenerator`: gera alternativa livre, com reasoning.
- `FireworksAuditor`: aprova alternativa ou substitui resposta.
- `TokenUsage`: metricas de tokens remotos.

## Contrato mental

```text
M1 = resposta livre, estado natural rapido
M2A = juiz estruturado, com rubrica e JSON
M2B = resposta livre, estado natural com reasoning
Fireworks = auditor externo forte, approve-or-replace
```

## Nao fazer aqui

- UI.
- HTML.
- Dashboard.
- Codigo especifico de um evaluator ainda desconhecido.
- Dependencia direta em paths de AMD/DigitalOcean.

