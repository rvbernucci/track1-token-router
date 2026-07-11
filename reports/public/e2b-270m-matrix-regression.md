# E2B x FunctionGemma 270M Matrix Regression

## Population

- Questions available: `4,000`
- Valid 270M/E2B-label intersections: `3982`
- Invalid 270M assessments routed to Fireworks: `18`
- E2B correct: `1551` (`38.95%`)

## Out-of-fold selection

- Threshold: `0.70`
- Selected: `443` (`11.13%` coverage)
- Correct: `350` (`79.01%` precision)
- Wilson 95% lower bound: `74.97%`
- Brier score: `0.1989`

## Strongest coefficients

- `score.generation_demand`: coefficient `-1.3777`, odds ratio `0.252`
- `intent.sentiment`: coefficient `1.1972`, odds ratio `3.311`
- `intent.math_reasoning`: coefficient `-0.9409`, odds ratio `0.390`
- `intent.logic_puzzle`: coefficient `-0.6530`, odds ratio `0.520`
- `intent.code_generation`: coefficient `-0.5801`, odds ratio `0.560`
- `intent.summarization`: coefficient `0.5113`, odds ratio `1.668`
- `intent.factual_qa`: coefficient `0.5001`, odds ratio `1.649`
- `score.reasoning_demand`: coefficient `-0.2620`, odds ratio `0.769`
- `intent.ner`: coefficient `0.2145`, odds ratio `1.239`
- `score.deterministic_fit`: coefficient `0.1119`, odds ratio `1.118`

## V2 model comparison

- Post-contract correct answers: `828`
- Correct answers with valid 270M parameters: `823`
- Champion: `per_intent_five_scores`

- `global_joint`: Brier `0.1934`, selected `248`, precision `84.68%`, coverage `12.46%`
- `per_intent_five_scores`: Brier `0.1880`, selected `252`, precision `84.52%`, coverage `12.66%`
- `univariate_deterministic_fit`: Brier `0.2414`, selected `1160`, precision `45.09%`, coverage `58.26%`
- `univariate_format_complexity`: Brier `0.2430`, selected `1505`, precision `43.06%`, coverage `75.59%`
- `univariate_generation_demand`: Brier `0.2336`, selected `1011`, precision `49.95%`, coverage `50.78%`
- `univariate_knowledge_uncertainty`: Brier `0.2431`, selected `1991`, precision `41.34%`, coverage `100.00%`
- `univariate_reasoning_demand`: Brier `0.2430`, selected `1984`, precision `41.43%`, coverage `99.65%`

The final coefficient matrix is fitted on all 3,982 usable rows. It remains disabled by default until its routing threshold is accepted against the accuracy gate.
