# Job-fit eval: testing an LLM judge before it goes to production

An LLM reads a job posting plus a candidate's profile and resume, and decides whether the role belongs in the candidate's job tracker: **add or skip**, a fit rating, and the main gap. This repo is the evaluation harness I used to build that judge, compare prompt versions and models, and decide what goes to production.

The judge runs every morning in my (private) job-search agent: code pulls new postings from company job boards, the tested prompt judges each one, and matches are added to a tracker.

## How it's tested

- **Test set:** 44 real postings, frozen and hand-labeled (23 add, 21 skip) with the right decision, fit, main gap and skip reason (`data/`).
- **Code-based grading:** `evals/scoring.py` grades every answer against the labels: decision accuracy, precision, recall, missed good jobs (false skips), valid output, cost and speed.
- **Regression check:** `evals/compare.py` compares two versions posting by posting and lists what each change fixed and what it broke.
- **Promotion rule, written before testing:** a version ships only if it has zero missed good jobs in every run, 100% valid output, no new regressions, and accuracy at least as high as the current version. Missing a good job costs far more than dismissing a bad one.
- **One change at a time:** each prompt version changes exactly one rule, and every version is rerun on the full set.

Full definitions and notes: [`EXPERIMENTS.md`](EXPERIMENTS.md).

## Results

| Version | What changed | Decision accuracy | Precision | Recall | Missed good jobs |
|---|---|---|---|---|---|
| v0 | Keyword rules, no AI | 77.3% | 71.0% | 95.7% | 1 |
| v1 | First Claude prompt | 88.6% | 82.1% | 100% | 0 |
| v2 | Clearer seniority and sales rules | 97.7% | 100% | 95.7% | 1 |
| v3 | Coding rule decided by job title | 97.7% | 95.8% | 100% | 0 |
| **v4** | **Coding rule decided by how much coding the job requires** | **100%** | **100%** | **100%** | **0** |

**What the numbers hid:**
- **v1 → v2** looks like a simple 9-point gain, but precision and recall show a trade: 5 junk adds removed, 1 good job missed. Under the zero-missed-jobs rule, v2 wouldn't have shipped.
- **v2 → v3** kept exactly the same score (43/44), but the regression check showed it fixed one posting and broke another. Only the posting-by-posting comparison caught it.
- **v4** fixed both: 44/44, with no regressions.

### Model comparison (prompt v4, 3 runs each)

| Model | Avg accuracy (range) | Missed good jobs (3 runs) | Valid output | $ per 1,000 postings |
|---|---|---|---|---|
| Claude Sonnet 5.5 | 100% (100–100) | 0 | 100% | $13.07 |
| Claude Haiku 5.5 | 98.5% (97.7–100) | 2 | 100% | $0.80 |
| DeepSeek V4.1 Flash | 95.5% (93.2–97.7) | 6 | 95.5% | $0.64 |
| Keyword rules | 77.3% | 1 (1 run) | 100% | $0 |

Only Sonnet passes the promotion rule. Haiku is about 16× cheaper but missed good jobs. v4 was tuned on Sonnet, so this comparison favors it; a prompt tuned for Haiku is a next step. Details: [`results/model_comparison.md`](results/model_comparison.md).

## Run it

Requires Python 3 (standard library only) and an [OpenRouter](https://openrouter.ai) key, so any model can be swapped in by name.

```bash
cp .env.example .env                                  # add your OPENROUTER_API_KEY
cp context/profile.example.md context/profile.md      # or write your own
cp context/resume.example.md context/resume.md

python3 evals/run_eval.py --model rules                                   # no-AI baseline, free
python3 evals/run_eval.py --model anthropic/claude-sonnet-5.5 --prompt v4 # any OpenRouter model id

# compare two saved runs posting by posting (no API calls)
python3 evals/compare.py results/20261109-0844_anthropic_claude-sonnet-5.5_v2.jsonl \
                         results/20261115-2242_anthropic_claude-sonnet-5.5_v3.jsonl
```

Saved results keep each answer's decision, fit, gap and scores; the model's free-text explanations were removed because they discuss a real resume. Rerunning with the example profile and resume will give different fit and gap answers than the saved runs.

## Repo layout

- `prompts/`: the four judge prompts (v1–v4)
- `data/`: the 44 postings (`scenarios.jsonl`) and labels (`labels.csv`)
- `evals/`: running, scoring, comparing and rescoring
- `results/`: saved runs and the model comparison
- `pipeline/judge_candidates.py`: how the tested v4 prompt is used in the daily job check (paths refer to the private project's layout)

## Next steps

- **Gap category is 61%.** All 9 misses say "domain"; the definitions don't separate preferred from required experience or say which gap wins when there are several.
- A blind held-out set, labeled before running.
- Tracing for the daily runs, so real mistakes feed back into the test set.
