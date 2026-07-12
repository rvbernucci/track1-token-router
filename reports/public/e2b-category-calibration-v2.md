# E2B Category Calibration V2

- Fit rows: `4047`
- Calibration rows: `1157`
- Protected rows not used: `1641`

## Category Candidates

- `factual_qa`: nominated, champion `enriched`, precision `90.62%`, coverage `34.78%`, Wilson lower `75.78%`
- `math_reasoning`: disabled, champion `enriched`, precision `0.00%`, coverage `0.00%`, Wilson lower `0.00%`
- `sentiment`: nominated, champion `enriched`, precision `85.05%`, coverage `75.89%`, Wilson lower `77.08%`
- `summarization`: disabled, champion `enriched`, precision `0.00%`, coverage `0.00%`, Wilson lower `0.00%`
- `ner`: nominated, champion `enriched`, precision `85.71%`, coverage `19.23%`, Wilson lower `70.62%`
- `code_debugging`: disabled, champion `enriched`, precision `0.00%`, coverage `0.00%`, Wilson lower `0.00%`
- `logic_puzzle`: disabled, champion `enriched`, precision `0.00%`, coverage `0.00%`, Wilson lower `0.00%`
- `code_generation`: disabled, champion `enriched`, precision `0.00%`, coverage `0.00%`, Wilson lower `0.00%`

## Sealed Holdout

- `factual_qa`: rejected, selected `10`, precision `90.00%`, Wilson lower `59.58%`
- `sentiment`: promoted, selected `46`, precision `95.65%`, Wilson lower `85.47%`
- `ner`: rejected, selected `9`, precision `100.00%`, Wilson lower `70.09%`

The holdout was opened once after the candidate decision surface was hash-frozen. Only categories that passed every support, precision, Wilson and subgroup gate are enabled.
