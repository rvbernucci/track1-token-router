# Fireworks LoRA & Fine-Tuning Strategy

Atualizado em: 2026-07-09

## Decisao de campeonato

LoRA nao deve entrar no caminho principal de submissao do Track 1 sem confirmacao explicita do avaliador.

Motivo: o Track 1 restringe a selecao a `ALLOWED_MODELS`, enquanto a documentacao Fireworks diz que modelos LoRA fine-tuned so podem ser implantados em on-demand dedicated deployments, nao em Serverless. Um LoRA em live merge ou multi-LoRA muda o `model` para um ID fine-tuned/deployment, potencialmente fora da lista permitida e fora da comparabilidade do scoring.

Portanto:

- caminho principal: solvers locais + matriz/Nash + modelos Fireworks permitidos;
- fine-tuning do roteador: permitido e compativel com o scoring, desde que a saida final continue respeitando accuracy e Fireworks token count;
- caminho LoRA como modelo de resposta: pesquisa/calibracao opcional, atras de feature flag, nunca default;
- uso competitivo: somente se o guia oficial ou harness expuser um LoRA/fine-tuned model em `ALLOWED_MODELS`.

## Distincao importante

O texto oficial permite fine-tunar o roteador. Isso e diferente de trocar o modelo de resposta por um LoRA Fireworks fora do conjunto permitido.

Seguro e alinhado:

- treinar uma regressao/matriz local para escolher o menor modelo suficiente;
- fine-tunar um classificador local que decide `local_solver`, `cheap_fireworks`, `strong_fireworks` ou `abstain`;
- calibrar thresholds de risco com dados de microbench;
- usar o fine-tuned router para reduzir chamadas Fireworks sem mudar os modelos finais permitidos.

Condicionado ao harness:

- chamar um fine-tuned Fireworks model como resposta final;
- usar multi-LoRA com `model="<fine_tuned_model>#<deployment>"`;
- substituir `minimax-m3`, `kimi-k2p7-code` ou Gemma permitido por um deployment proprio.

Regra pratica: fine-tunar a decisao de roteamento e bom; fine-tunar o modelo respondedor so entra se o avaliador aceitar esse endpoint/model ID.

## O que a documentacao oficial diz

Fontes:

- Fireworks Managed Fine-Tuning Overview: https://docs.fireworks.ai/fine-tuning/managed-finetuning-intro
- Fireworks Deploying Fine Tuned Models: https://docs.fireworks.ai/fine-tuning/deploying-loras
- Fireworks Understanding LoRA Performance: https://docs.fireworks.ai/guides/understanding_lora_performance
- Fireworks Model Library: https://app.fireworks.ai/models

Pontos relevantes:

- Managed fine-tuning suporta familias abertas importantes, incluindo Gemma, Kimi, DeepSeek, Qwen, GLM e Llama, quando o base model tem training shape compativel.
- Gemma `gemma-4-26b-a4b-it` e `gemma-4-31b-it` aparecem na tabela de fine-tuning com contexto maximo de `256K`.
- LoRA e recomendado quando queremos adapter training eficiente e flexibilidade para servir multiplos adapters.
- Full-parameter tuning e indicado quando a tarefa exige alterar todos os pesos para raciocinio, alinhamento ou adaptacao de dominio dificil.
- LoRA fine-tuned models so podem ser deployed em on-demand dedicated deployments; Fireworks afirma que Serverless nao suporta LoRA.
- Fireworks oferece dois modos de deploy LoRA: live merge e multi-LoRA.
- Live merge funde os pesos LoRA no deploy, removendo overhead de inferencia e igualando comportamento de um fine-tune nativo.
- Multi-LoRA permite varios adapters em um unico deployment, mas adiciona overhead por request.
- Para multi-LoRA, o request deve usar `model="<fine_tuned_model>#<deployment>"`; a chave antiga `deployedModel` esta depreciada.
- FP8/FP4 quantized shapes nao suportam `--enable-addons`; LoRA addon requer BF16 ou merge.
- LoRA unmerged pode aumentar TTFT em torno de `10-30%` e reduzir throughput sob concorrencia.

## Fit com Track 1

Track 1 premia menor token count depois do accuracy gate. Fine-tuning do roteador pode reduzir tokens se ele evita chamadas ou escolhe modelos menores com seguranca. Fine-tuning do modelo respondedor pode melhorar accuracy de um modelo pequeno, mas nao reduz tokens automaticamente:

- os tokens Fireworks continuam contando se a inferencia passa por `FIREWORKS_BASE_URL`;
- se o LoRA exigir deployment proprio, ele pode sair do conjunto oficial de modelos permitidos;
- se a resposta local ja cobre subcasos mecanicos com zero token, LoRA compete contra uma opcao melhor: nao chamar Fireworks;
- se o problema e roteamento, um modelo fine-tuned ainda precisa receber prompt e produzir resposta, entao pode gastar mais token do que uma regra/solver local.

Conclusao: LoRA so faria sentido para a faixa residual de tarefas que:

- nao sao mecanicamente resolviveis;
- aparecem com padrao repetido no avaliador;
- hoje exigem modelo caro para passar accuracy;
- podem ser respondidas por um modelo menor/fine-tuned com menos tokens;
- e sao aceitas pelo harness como modelo permitido.

## Usos seguros agora

Sem depender de aceitacao oficial:

- estudar a Model Library para ver quais modelos permitidos sao tunable/deployable;
- preparar um dataset SFT de roteamento/format-following a partir dos microbenches locais;
- usar LoRA apenas como laboratorio para medir se Gemma/Minimax/Kimi melhora em formato estrito;
- nao publicar imagem final apontando para LoRA;
- nao alterar `ALLOWED_MODELS` para ID fine-tuned no caminho de submissao.

## Feature flag proposta

Se o regulamento liberar fine-tuned deployments, implementar atras destas variaveis:

```bash
ENABLE_FIREWORKS_LORA=0
FIREWORKS_LORA_MODEL=
FIREWORKS_LORA_DEPLOYMENT=
FIREWORKS_LORA_MODE=disabled  # disabled|live_merge|multi_lora
```

Regras:

- default sempre `disabled`;
- falhar fechado se `FIREWORKS_LORA_MODEL` nao estiver em `ALLOWED_MODELS` ou se `ALLOW_UNLISTED_LORA=1` nao estiver explicitamente definido para laboratorio;
- registrar em metadata quando LoRA for usado;
- separar custo/latencia/validade de LoRA nos relatórios para nao contaminar matriz oficial.

## Experimento minimo se liberarem

1. Criar dataset de SFT com entradas do tipo `prompt -> answer` apenas para formato estrito e categorias onde Fireworks falha por wrappers/extraneous prose.
2. Treinar LoRA curto em um base permitido, preferencialmente Gemma se o bonus Gemma continuar relevante.
3. Deploy live merge, nao multi-LoRA, se houver apenas um adapter; isso evita overhead.
4. Rodar `scripts/fireworks_microbench.py` no mesmo dataset dos modelos permitidos.
5. Aceitar LoRA apenas se passar estes gates:

- validade mecanica maior ou igual ao melhor modelo permitido;
- tokens totais menores que o melhor modelo permitido na mesma categoria;
- latencia dentro do budget oficial;
- ID aceito pelo harness ou explicitamente listado em `ALLOWED_MODELS`;
- auditoria de submissao documenta o risco regulatorio.

## Decisao atual

Nao implementar LoRA no runtime principal agora.

Melhor retorno competitivo imediato:

- ampliar gates adversariais zero-token;
- manter Gemma no projeto via modelos permitidos/local AMD quando acessivel;
- usar Fireworks allowed models como fallback controlado por matriz/regressao/Nash;
- gastar credito apenas em microbench que melhora pesos de roteamento ou revela falhas de solvers/formatos.
