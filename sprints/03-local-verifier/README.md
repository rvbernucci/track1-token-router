# Sprint 03 - Verificador M2A e M2B

## Objetivo

Construir a cascata local: `M2A` valida o candidato do `M1`; se houver risco, `M2B` gera uma alternativa local com reasoning/resonancia.

Esta e a sprint onde a arquitetura deixa de ser "uma chamada local" e vira triagem real.

## Entregaveis

- Prompt `m2a_verify_candidate`.
- Saida estruturada pequena para decisao local.
- Parser robusto de `approve/escalate`.
- Prompt `m2b_repair_answer`.
- Cascata local completa.
- Logs comparando M1, decisao M2A e alternativa M2B.

## Checklist

- [ ] Criar `LocalVerifier`.
- [ ] Criar envelope seguro para `task` + `model_1_candidate_raw`.
- [ ] Definir schema JSON minimo do M2A.
- [ ] Validar schema com fallback se o modelo emitir JSON invalido.
- [ ] Criar rubrica fixa do M2A.
- [ ] Incluir criterios de erro: formato, factualidade, matematica, instrucao, ambiguidade.
- [ ] Evitar chain-of-thought no log.
- [ ] Criar `LocalRepairGenerator` para M2B.
- [ ] Fazer M2B emitir resposta livre, nao JSON.
- [ ] Registrar rota `m1_approved` ou `m2b_candidate`.
- [ ] Testar casos faceis que M2A deve aprovar.
- [ ] Testar casos dificeis que M2A deve escalar.

## Schema M2A alvo

```json
{
  "decision": "approve",
  "confidence": "high",
  "reason": "short reason without hidden reasoning",
  "failure_modes": [],
  "should_generate_alternative": false
}
```

## Criterios de aceite

- Perguntas triviais passam por M1 e sao aprovadas pelo M2A.
- Perguntas com resposta ruim sao escaladas para M2B.
- M2B consegue gerar alternativa livre sem contaminar formato.
- O runner nunca entrega o JSON do M2A ao usuario final.
- Logs permitem auditar por que uma rota foi escolhida.

## Rubrica M2A

M2A deve escalar quando houver:

- calculo nao trivial ou multi-etapa;
- pedido de alta precisao;
- pergunta factual que pode estar desatualizada;
- instrucao de formato que M1 nao cumpriu;
- contradicao interna na resposta;
- resposta excessivamente generica;
- risco de safety/compliance;
- ambiguidade que exige resposta mais cuidadosa.

M2A deve aprovar quando:

- a tarefa for saudacao, reformulacao simples ou resposta direta;
- a resposta seguir claramente o formato pedido;
- o risco de erro factual for baixo;
- a alternativa local provavelmente nao melhoraria;
- chamar Fireworks seria desperdicio de token.

## Riscos

- M2A escalar demais e queimar tokens depois.
- M2A aprovar respostas erradas com muita confianca.
- M2B produzir resposta mais bonita, mas menos correta.
- O prompt fixo do M2A ficar grande demais e lento.

## Experimentos

- Rubrica curta vs rubrica longa.
- M2A com output `approve/escalate` apenas vs schema com failure modes.
- M2B sempre acionado em escalate vs M2B pulado em erros obvios.
- Limite de tokens do M2A agressivo vs confortavel.

## Saida esperada da sprint

Uma cascata local funcional que ja reduz risco antes de gastar qualquer token remoto.

