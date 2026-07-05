# Sprint 02 - Modelo local e M1

## Objetivo

Conectar o modelo local e fazer o `M1` gerar candidatos livres, sem reasoning/resonancia e sem formato artificial.

O `M1` e o trabalhador rapido: ele tenta responder bem com o minimo de friccao.

## Entregaveis

- Cliente OpenAI-compatible para modelo local.
- Configuracao por `LOCAL_BASE_URL` e `LOCAL_MODEL`.
- Prompt simples do `M1`.
- Baseline local sem Fireworks.
- Dataset pequeno de smoke tests.
- Metricas de latencia local.

## Checklist

- [x] Criar `LocalModelClient`.
- [x] Suportar timeout e retry simples.
- [x] Separar system prompt, user prompt e parametros.
- [x] Criar prompt `m1_free_answer`.
- [x] Preservar resposta livre exatamente como candidata final.
- [x] Registrar `model_1_candidate_raw` no log.
- [x] Medir latencia do M1.
- [x] Criar smoke tests para perguntas triviais.
- [x] Criar smoke tests para formato exigido pelo usuario.
- [x] Criar smoke tests para prompts longos.
- [x] Criar fallback quando o modelo local falhar.

## Criterios de aceite

- [x] `router ask "What is 2+2?"` chama o modelo local real.
- [x] A resposta do M1 nao vem embrulhada em JSON/XML por padrao.
- [x] O log registra input hash, rota, latencia e tamanho aproximado da resposta.
- [x] Falha do modelo local nao derruba o processo sem mensagem controlada.

## Evidencias

- `python3 -m unittest discover -s tests`
- `ROUTER_MODE=local LOCAL_BASE_URL=<openai-compatible-url> LOCAL_MODEL=<model> python3 -m router ask "What is 2+2?"`
- `evals/smoke/local_m1_tasks.jsonl`

## Prompt M1

Principio:

- responder diretamente a tarefa;
- seguir o formato pedido pelo usuario;
- nao explicar demais quando a tarefa pede concisao;
- nao mencionar arquitetura interna;
- nao emitir JSON/XML a menos que a tarefa original peça.

## Riscos

- M1 ficar verboso demais e prejudicar avaliacao.
- M1 ignorar formatos especificos.
- Timeout local comprometer throughput.
- Parametros ruins de temperatura gerarem instabilidade.

## Experimentos

- Temperatura baixa vs media.
- System prompt minimo vs prompt com regras de formato.
- Limite de output curto vs medio.
- Parar cedo em tarefas triviais.

## Saida esperada da sprint

Um baseline local completo: barato, simples, medido e capaz de responder do inicio ao fim sem Fireworks.
