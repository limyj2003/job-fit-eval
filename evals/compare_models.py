"""Compare models on one prompt version, with a hard spending limit.

Runs evals/run_eval.py once per planned run, then prints one table with a row per
model and saves it to results/model_comparison.md. All runs are graded with
scoring.py against the current labels.

Finished runs are remembered in results/model_comparison_runs.json, so running this
again continues where it stopped and never pays for a finished run twice.

Spending limit: only new runs count. Before each run, the script adds that run's
worst-case cost to the total so far and stops if the result would pass the limit.

Usage:
  python3 evals/compare_models.py --dry-run   # show the plan and costs; no paid calls
  python3 evals/compare_models.py
"""
import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_eval  # noqa: E402
import scoring  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")
MANIFEST = os.path.join(RESULTS, "model_comparison_runs.json")
TABLE = os.path.join(RESULTS, "model_comparison.md")

PROMPT = "v4"
BUDGET_USD = 3.50
MAX_REPLY_TOKENS = 2000  # the reply limit set in llm_client.chat
INPUT_SAFETY_MARGIN = 1.25  # characters / 4 is only an estimate of tokens
EXISTING_RUNS = {"anthropic/claude-sonnet-5.5": ["20261115-2307_anthropic_claude-sonnet-5.5_v4.jsonl"]}

# Cheapest first, so the expensive runs happen only after the others have worked.
PLAN = [
    ("rules", 1),
    ("anthropic/claude-haiku-5.5", 3),
    ("deepseek/deepseek-v4.1-flash-1017", 3),
    ("anthropic/claude-sonnet-5.5", 3),  # includes the existing run
]


def load_manifest():
    if os.path.exists(MANIFEST):
        return json.load(open(MANIFEST))
    return {"prompt": PROMPT, "runs": [{"model": model, "file": name, "new": False, "ok": True}
                                       for model, names in EXISTING_RUNS.items() for name in names]}


def save_manifest(manifest):
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=1)


def load_rows(name, labels):
    """Read one results file and grade every posting against the current labels."""
    lines = open(os.path.join(RESULTS, name)).read().splitlines()
    head, rows = json.loads(lines[0]), [json.loads(line) for line in lines[1:]]
    for r in rows:
        r["label"] = labels[r["id"]]
        r["scores"] = scoring.score_one(r["label"], r["out"])
    return head, rows


def run_cost(rows):
    return sum(r.get("cost") or 0 for r in rows)


def run_problem(head, rows, model, expected):
    if head.get("model") != model or head.get("prompt") != PROMPT:
        return f"file is for {head.get('model')} prompt {head.get('prompt')}"
    if len(rows) != expected:
        return f"has {len(rows)} postings, expected {expected}"
    errors = sum(r["raw"].startswith("ERROR") for r in rows)
    return f"{errors} postings failed with API errors" if errors else None


def model_prices():
    text = subprocess.run(["curl", "-sS", "-m", "40", "https://openrouter.ai/api/v1/models"],
                          capture_output=True, text=True).stdout
    return {m["id"]: m["pricing"] for m in json.loads(text)["data"]}


def worst_case_cost(model, prices, scenarios):
    """Cost if the input estimate runs high and every reply hits the token limit."""
    if model == "rules":
        return 0.0
    system = open(os.path.join(HERE, "prompts", f"judge_{PROMPT}.md")).read()
    chars = sum(len(system) + len(run_eval.build_user_message(s)) for s in scenarios)
    input_tokens = chars / 4 * INPUT_SAFETY_MARGIN
    output_tokens = len(scenarios) * MAX_REPLY_TOKENS
    return input_tokens * float(prices[model]["prompt"]) + output_tokens * float(prices[model]["completion"])


def run_once(model):
    """Run run_eval.py once and return the name of the results file it created."""
    before = set(glob.glob(os.path.join(RESULTS, "*.jsonl")))
    script = os.path.join(HERE, "evals", "run_eval.py")
    code = subprocess.run([sys.executable, script, "--model", model, "--prompt", PROMPT], cwd=HERE).returncode
    created = set(glob.glob(os.path.join(RESULTS, "*.jsonl"))) - before
    if code != 0 or len(created) != 1:
        raise RuntimeError(f"run_eval.py exit code {code}; {len(created)} new results files")
    return os.path.basename(created.pop())


def percent(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def build_table(manifest, labels):
    header = ["Model", "Runs", "Decision accuracy (avg)", "Min–max", "Precision", "Recall",
              "False skips (total)", "Valid output", "Cost per 1,000 postings", "Avg seconds per posting"]
    table = [header]
    for model, _ in PLAN:
        runs = [load_rows(r["file"], labels)[1] for r in manifest["runs"] if r["model"] == model and r["ok"]]
        if not runs:
            continue
        accuracy = [scoring.summarize(rows)["decision"][0] for rows in runs]
        rows = [row for run in runs for row in run]
        s = scoring.summarize(rows)  # all runs pooled, so false skips are a total
        costs = [r["cost"] for r in rows if r.get("cost") is not None]
        per_1000 = 0.0 if model == "rules" else (sum(costs) / len(costs) * 1000 if costs else None)
        seconds = "under 0.1" if model == "rules" else ("n/a" if s["avg_seconds"] is None else f"{s['avg_seconds']:.1f}")
        table.append([model, str(len(runs)), percent(sum(accuracy) / len(accuracy)),
                      f"{percent(min(accuracy))}–{percent(max(accuracy))}", percent(s["add_precision"][0]),
                      percent(s["add_recall"][0]), str(s["false_skips"]), percent(s["valid"][0]),
                      "n/a" if per_1000 is None else f"${per_1000:.2f}", seconds])
    return table


def markdown(table):
    lines = ["| " + " | ".join(row) + " |" for row in table]
    lines.insert(1, "|" + "---|" * len(table[0]))
    return "\n".join(lines)


def report(manifest, labels, spent, stop_reason):
    table = build_table(manifest, labels)
    text = markdown(table)
    print("\n" + text)
    print(f"\nNew spending this comparison: ${spent:.4f} (limit ${BUDGET_USD:.2f})")
    done = {m: sum(r["model"] == m and r["ok"] for r in manifest["runs"]) for m, _ in PLAN}
    complete = all(done[m] >= n for m, n in PLAN)
    notes = [f"# Model comparison: prompt {PROMPT}", "",
             f"Updated {datetime.now():%Y-%m-%d %H:%M}. 44 frozen postings, graded by `evals/scoring.py` "
             "against the current `data/labels.csv`.", "", text, "",
             "- Decision accuracy is the average across runs; min–max shows how much it moved between runs.",
             "- Precision, recall and valid output pool all of a model's runs. False skips are totaled across runs.",
             "- Prompt v4 was tuned on these same postings using Claude Sonnet 5.5, so this comparison favors Sonnet.",
             f"- New spending: ${spent:.4f}. The existing Sonnet run is not counted as new spending.", ""]
    if not complete or stop_reason:
        notes.append(f"**Incomplete:** {stop_reason or 'not all planned runs have finished.'}\n")
    notes += ["Runs used:", ""] + [f"- `{r['model']}`: `{r['file']}`" for r in manifest["runs"] if r["ok"]] + [""]
    with open(TABLE, "w") as f:
        f.write("\n".join(notes))
    print(f"Saved to {os.path.relpath(TABLE, HERE)}")


def main(dry_run):
    labels = scoring.load_labels()
    scenarios = run_eval.load_scenarios()
    manifest = load_manifest()
    for r in manifest["runs"]:  # refuse to build on a bad or mismatched file
        head, rows = load_rows(r["file"], labels)
        problem = run_problem(head, rows, r["model"], len(scenarios))
        if r["ok"] and problem:
            sys.exit(f"Cannot use {r['file']}: {problem}")
    prices = model_prices()
    spent = sum(run_cost(load_rows(r["file"], labels)[1]) for r in manifest["runs"] if r["new"])
    stop_reason = None

    for model, wanted in PLAN:
        worst = worst_case_cost(model, prices, scenarios)
        have = sum(r["model"] == model and r["ok"] for r in manifest["runs"])
        print(f"{model}: {have}/{wanted} runs done; worst case ${worst:.3f} per new run", flush=True)
        if dry_run:
            continue
        while have < wanted and not stop_reason:
            if spent + worst > BUDGET_USD:
                stop_reason = (f"the next {model} run could cost up to ${worst:.2f}, which would take spending "
                               f"from ${spent:.2f} past ${BUDGET_USD:.2f}.")
                break
            print(f"\n=== Starting {model}, run {have + 1} of {wanted} ===", flush=True)
            try:
                name = run_once(model)
            except RuntimeError as e:
                stop_reason = f"{model} run failed: {e}"
                break
            head, rows = load_rows(name, labels)
            cost = run_cost(rows)
            spent += cost
            problem = run_problem(head, rows, model, len(scenarios))
            manifest["runs"].append({"model": model, "file": name, "new": True, "ok": not problem})
            save_manifest(manifest)
            print(f"Run cost ${cost:.4f}; new spending so far ${spent:.4f}", flush=True)
            if problem:
                stop_reason = f"{model} run not counted: {problem}."
            elif spent > BUDGET_USD:
                stop_reason = f"spending reached ${spent:.2f}, past the ${BUDGET_USD:.2f} limit."
            have += 1
        if stop_reason:
            break

    if dry_run:
        print("\nDry run: no paid calls made and nothing saved.")
        print(markdown(build_table(manifest, labels)))
        return 0
    save_manifest(manifest)
    report(manifest, labels, spent, stop_reason)
    if stop_reason:
        print(f"\nSTOPPED: {stop_reason}")
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare models on prompt v4.")
    parser.add_argument("--dry-run", action="store_true", help="show the plan and costs; make no paid calls")
    sys.exit(main(parser.parse_args().dry_run))
