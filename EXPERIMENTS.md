# Experiment log

## How every version is scored

Test set: 44 real postings frozen on 2026-11-09, hand-labeled (23 add, 21 skip). Every version runs on the same set, scored by `evals/scoring.py`.

| Metric | Counts as correct when… | Out of… |
|---|---|---|
| Valid output | Reply is readable JSON and every field uses an allowed value | All 44 |
| Decision accuracy | Add/skip matches my label | All 44 |
| Precision | Of the postings it added, the ones I labeled add | Postings it added |
| Recall | Of the postings I labeled add, the ones it added | 23 add labels |
| False skips | (count) Postings I labeled add that it skipped | 23 add labels |
| Fit exact / within one | Fit matches my label / is at most one level off | 23 add labels |
| Gap category | Main gap matches my label | 23 add labels |
| Skip reason | Skip reason matches my label | 21 skip labels |
| Cost / speed | $ per 1,000 postings / average seconds per posting | All 44 |

Notes: an unreadable reply counts as a wrong decision. Fit and gap are scored on my 23 add labels, so a wrongly skipped good job also counts against fit and gap.

## Promotion rule (decided before running, applied to every new version)

A version replaces the current one only if, across 3 runs:
1. **Valid output is 100%.** Code must be able to read every reply.
2. **Zero false skips (recall 100%) in every run.** Missing a good job costs far more than dismissing a bad one.
3. **No new regressions** vs. the current version, unless I check the posting and confirm my label was wrong.
4. **Decision accuracy is at least as high** as the current version's.

Among versions that pass: pick the **highest precision**, then the **lowest cost**, then the **fastest**.

Fit and gap category are tracked but don't decide promotion: the add/skip decision is what changes what I see.

Task: **job-fit judge**. Given one job posting plus my profile and resume, decide add/skip, rate the fit, and name the main gap.
Dataset: 44 real postings frozen on 2026-11-09 (23 add, 21 skip). Labels are in `data/labels.csv`.

Rule: change one thing at a time, rerun the full set, and record the result here.

Scores below use **labels v2**: the answer key after 4 label changes (see notes). Older runs were re-scored with `evals/rescore.py`; the models' answers didn't change.

| # | Date | Model | Prompt | Change | Decision acc. | Precision | Recall | False skips | Fit exact | Fit ±1 | Gap | Skip reason | Valid | $/run | s/posting |
|---|------|-------|--------|--------|---------------|-----------|--------|-------------|-----------|--------|-----|-------------|-------|-------|-----------|
| v0 | 2026-11-09 | rules (no AI) | – | Keyword rules, like the daily job check script | 77.3% | 71.0% (22/31) | 95.7% (22/23) | 1 | 65.2% | 91.3% | 73.9% | 57.1% | 100% | $0 | ~0 |
| v1 | 2026-11-09 | claude-sonnet-5.5 | v1 | Baseline prompt (`prompts/judge_v1.md`) | 88.6% | 82.1% (23/28) | 100% (23/23) | 0 | 65.2% | 100% | 56.5% | 71.4% | 100% | $0.60 | 3.0 |
| v2 | 2026-11-09 | claude-sonnet-5.5 | v2 | Only the skip rules changed: "3+ years = skip", growth/outreach roles = skip | 97.7% | 100% (22/22) | 95.7% (22/23) | 1 | 65.2% | 95.7% | 52.2% | 95.2% | 100% | $0.56 | 2.4 |
| v3 | 2026-11-15 | claude-sonnet-5.5 | v3 | Only the coding rule changed: "not an engineering title = add" | 97.7% | 95.8% (23/24) | 100% (23/23) | 0 | 65.2% | 100% | 60.9% | 90.5% | 100% | $0.58 | 2.6 |
| v4 | 2026-11-15 | claude-sonnet-5.5 | v4 | Coding rule based on how much coding the job requires, not the title | **100%** | 100% (23/23) | 100% (23/23) | 0 | 65.2% | 100% | 60.9% | 95.2% | 100% | $0.57 | 2.3 |

How to read the new columns:
- **Precision:** of the roles the model added, the share that should be added. Low precision means junk in the tracker.
- **Recall:** of the roles that should be added, the share the model added.
- **False skips:** roles labeled add that the model didn't add: good jobs that would never reach the tracker. A missing or unreadable answer also counts as a false skip.

`evals/compare.py` lists the postings behind each change. From v1 to v2, 5 were fixed (s15, s23, s31, s40, s41, all "should skip") and 1 regressed (s04 Loop, now a false skip). v2 traded one false skip for zero false adds.

Original scores against labels v1, before the fixes: v0 86.4%, v1 88.6%.

## Notes

### v0: rules baseline
- Misses "too senior" roles when the years requirement is phrased unusually.
- Can't tell "STEM degree required" from "technical degree preferred."

### v1: Claude Sonnet 5.5 baseline
Two harness bugs were found and fixed before this run counted. Both were run problems, not model quality:
- **Rate limit:** OpenRouter caps new accounts at 20 requests per minute. Fix: retry with backoff, and space requests ≥3.2s apart.
- **Reply cap:** one answer was cut off at 800 tokens. Fix: raised `max_tokens` to 2000.

The 5 wrong decisions split into two kinds:
- **3 were label errors that Claude caught.** I checked each posting against Claude's explanation, and the labels are under review:
  - **s13, Mercor Research Ops, Code:** the posting requires a CS/STEM degree, so it should be a skip under my own STEM rule.
  - **s26, Mercor Program Manager, Quality:** the posting includes managing a 30+ person auditor workforce.
  - **s31, Mercor Growth Associate:** the job is expert sourcing and recruiting, not sales.
- **2 come from a rule that's unclear:** s40 and s41 ask for 3–5 years. The prompt says to skip only roles that "clearly require 4+ years," so Claude added them; my label says skip.

Other patterns:
- **Gap category is the weakest score (56%).** Claude often says "domain" where my label says "none" (6 cases). The categories need clearer definitions.
- **It under-rates fit:** 6 roles labeled high were rated medium.
- **Run-to-run variation:** on s04 (Loop), the same prompt at temperature 0 gave "skip/coding_required" in one run and "add/medium" in another. The scores have some noise, so one run isn't the final word.

### Label fixes (labels v1 → v2), decided by me on 2026-11-09 after reading the postings
- **s13, Mercor Research Ops, Code:** add → skip (stem_degree). Requires a CS/STEM degree with economics not listed. Also removed from my tracker.
- **s26, Mercor Program Manager, Quality:** add → skip (too_senior). 3+ years plus managing a 30+ person auditor workforce.
- **New rule: any role asking 3+ years at minimum is a skip.** This flipped two more labels:
  - s15, Vooma Deployment Strategist: add → skip
  - s23, Ramp Customer Activation: add → skip
- **s31, Mercor Growth Associate:** kept as skip. Growth and outreach roles aren't wanted, even when they're expert sourcing.
- **Caution:** fixing labels after seeing a model's answers can bias the answer key toward that model. Each fix was checked against the posting text, not Claude's explanation alone. A fresh held-out set would be a stronger test.

### v2: prompt rules updated to match the decisions
- **Decision accuracy rose from 88.6% to 97.7%.** All 4 too-senior misses and the growth-role miss were fixed.
- **The only remaining mistake is s04 (Loop).** Claude read "must read and write Python, git, terminal" as "coding required." That's the same flip-flop seen in v1, so the prompt needs a clearer line between using Python and engineering work.
- **Not fixed yet:**
  - **Gap category (52%):** the definitions of "none" vs. "domain" are still unclear.
  - **Fit rating (65% exact):** it under-rates "high."
  - These are candidates for v3, changing one thing at a time.

### v3: coding rule changed (one change)
- **Goal:** fix s04 (Loop), where v2 read "Python and git required" as an engineering job.
- **s04 check:** add 3/3 runs (fit medium, medium, high: fit varies on borderline postings even at temperature 0).
- **Full run vs. v2 (`compare.py`):** fixed s04, but **regressed s29** (Handshake, Strategic Projects Lead, Coding/Frontier), which requires strong coding skills, unit tests and CI.
- **Accuracy stayed at 97.7%,** so the total hid that one mistake was swapped for another.
- **Why:** the rule drew the line at the job title. Handshake's title isn't "engineer," so v3 added it.
- **Promotion rule:** fails rule 3 (new regression). Not promoted.

### v4: coding rule based on skill level (one change vs. v3)
- **Change:** skip when coding is a core part of the job or strong coding skills are required. Working familiarity (read/write Python or SQL, git, terminal) is a gap, not a skip.
- **Edge-case check:** s04 → add and s29 → skip, 3/3 runs each.
- **Full run:** 44/44 correct, 100% precision and recall, 0 false skips.
- **vs. v2 (`compare.py`):** fixed s04, 0 regressions.
- **Promotion rule:** passes on this run. To confirm: 3 runs per model (Monday) and a held-out set (Tuesday).
- **Not improved yet:** fit exact (65.2%) and gap category (60.9%). Expected, since only the coding rule changed. Next candidates.
