"""Run the job-fit judge over every scenario and score it.

Examples:
  python3 evals/run_eval.py --model rules                          # no-AI baseline
  python3 evals/run_eval.py --model anthropic/claude-sonnet-4.5    # any OpenRouter model id
  python3 evals/run_eval.py --model openai/gpt-5-mini --prompt v1 --limit 5

Results are saved to results/<date>_<model>_<prompt>.jsonl so runs can be compared later.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_scenarios():
    path = os.path.join(HERE, "data", "scenarios.jsonl")
    return [json.loads(line) for line in open(path)]


def build_user_message(scenario):
    profile = open(os.path.join(HERE, "context", "profile.md")).read()
    resume = open(os.path.join(HERE, "context", "resume.md")).read()
    return (f"PROFILE:\n{profile}\n\nRESUME:\n{resume}\n\nPOSTING:\n"
            f"Company: {scenario['company']}\nRole: {scenario['role']}\nLocation: {scenario['location']}\n\n"
            f"{scenario['posting_text']}")


def run(model, prompt_name, limit=None, ids=None):
    scenarios = load_scenarios()
    if ids:
        scenarios = [s for s in scenarios if s["id"] in ids]
    if limit:
        scenarios = scenarios[:limit]
    labels = scoring.load_labels()
    rows = []
    if model == "rules":
        import rules_baseline
        judge = lambda s: (rules_baseline.judge(s), None, None, "")  # noqa: E731
    else:
        import llm_client
        system = open(os.path.join(HERE, "prompts", f"judge_{prompt_name}.md")).read()

        def judge(s):
            text, secs, cost = llm_client.chat(model, system, build_user_message(s))
            return llm_client.parse_json(text) or {}, secs, cost, text

    for i, s in enumerate(scenarios, 1):
        try:
            out, secs, cost, raw = judge(s)
        except Exception as e:  # record the failure and keep going
            out, secs, cost, raw = {}, None, None, f"ERROR: {e}"
        label = labels[s["id"]]
        rows.append({"id": s["id"], "company": s["company"], "role": s["role"], "label": label,
                     "out": out, "raw": raw, "seconds": secs, "cost": cost,
                     "scores": scoring.score_one(label, out)})
        mark = "ok " if rows[-1]["scores"]["decision"] else "XX "
        print(f"{mark}{i:>2}/{len(scenarios)} {s['id']} {s['company']} | {s['role'][:45]} -> "
              f"{out.get('decision')}/{out.get('fit') or out.get('skip_reason')}", flush=True)

    summary = scoring.summarize(rows)
    summary["api_errors"] = sum(r["raw"].startswith("ERROR") for r in rows)
    name = f"{model} (prompt {prompt_name})" if model != "rules" else "rules baseline (no AI)"
    scoring.print_summary(name, summary)
    if summary["api_errors"]:
        print(f"\n  WARNING: {summary['api_errors']} postings failed with API errors and were scored as wrong. "
              "Rerun before trusting these numbers.")

    print("\nMistakes (decision wrong):")
    for r in rows:
        if not r["scores"]["decision"]:
            exp = r["label"]["expected_decision"] + "/" + (r["label"]["expected_fit"] or r["label"]["skip_reason"])
            got = f"{r['out'].get('decision')}/{r['out'].get('fit') or r['out'].get('skip_reason')}"
            print(f"  {r['id']} {r['company']} | {r['role'][:45]}: expected {exp}, got {got}")

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    safe = model.replace("/", "_").replace(":", "_")
    path = os.path.join(HERE, "results", f"{datetime.now():%Y%m%d-%H%M}_{safe}_{prompt_name}.jsonl")
    with open(path, "w") as f:
        f.write(json.dumps({"model": model, "prompt": prompt_name, "summary": summary}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nSaved to {os.path.relpath(path, HERE)}")
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help='"rules" or an OpenRouter model id')
    p.add_argument("--prompt", default="v1", help="prompt version: prompts/judge_<version>.md")
    p.add_argument("--limit", type=int, help="only run the first N scenarios")
    p.add_argument("--ids", nargs="*", help="only run these scenario ids, e.g. s01 s28")
    a = p.parse_args()
    run(a.model, a.prompt, a.limit, a.ids)
