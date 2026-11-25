# Model comparison: prompt v4

Updated 2026-11-18 14:50. 44 frozen postings, graded by `evals/scoring.py` against the current `data/labels.csv`.

| Model | Runs | Decision accuracy (avg) | Min–max | Precision | Recall | False skips (total) | Valid output | Cost per 1,000 postings | Avg seconds per posting |
|---|---|---|---|---|---|---|---|---|---|
| rules | 1 | 77.3% | 77.3%–77.3% | 71.0% | 95.7% | 1 | 100.0% | $0.00 | under 0.1 |
| anthropic/claude-haiku-5.5 | 3 | 98.5% | 97.7%–100.0% | 100.0% | 97.1% | 2 | 100.0% | $0.80 | 3.1 |
| deepseek/deepseek-v4.1-flash-1017 | 3 | 95.5% | 93.2%–97.7% | 100.0% | 91.3% | 6 | 95.5% | $0.64 | 4.6 |
| anthropic/claude-sonnet-5.5 | 3 | 100.0% | 100.0%–100.0% | 100.0% | 100.0% | 0 | 100.0% | $13.07 | 2.3 |

- Decision accuracy is the average across runs; min–max shows how much it moved between runs.
- Precision, recall and valid output pool all of a model's runs. False skips are totaled across runs.
- Prompt v4 was tuned on these same postings using Claude Sonnet 5.5, so this comparison favors Sonnet.
- New spending: $1.3431. The existing Sonnet run is not counted as new spending.

Runs used:

- `anthropic/claude-sonnet-5.5`: `20261115-2307_anthropic_claude-sonnet-5.5_v4.jsonl`
- `rules`: `20261118-1426_rules_v4.jsonl`
- `anthropic/claude-haiku-5.5`: `20261118-1428_anthropic_claude-haiku-5.5_v4.jsonl`
- `anthropic/claude-haiku-5.5`: `20261118-1431_anthropic_claude-haiku-5.5_v4.jsonl`
- `anthropic/claude-haiku-5.5`: `20261118-1434_anthropic_claude-haiku-5.5_v4.jsonl`
- `deepseek/deepseek-v4.1-flash-1017`: `20261118-1437_deepseek_deepseek-v4.1-flash-1017_v4.jsonl`
- `deepseek/deepseek-v4.1-flash-1017`: `20261118-1441_deepseek_deepseek-v4.1-flash-1017_v4.jsonl`
- `deepseek/deepseek-v4.1-flash-1017`: `20261118-1445_deepseek_deepseek-v4.1-flash-1017_v4.jsonl`
- `anthropic/claude-sonnet-5.5`: `20261118-1448_anthropic_claude-sonnet-5.5_v4.jsonl`
- `anthropic/claude-sonnet-5.5`: `20261118-1450_anthropic_claude-sonnet-5.5_v4.jsonl`
