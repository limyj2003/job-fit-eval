"""Judge the postings saved by `job_check.py fetch` with the tested v4 prompt.

Each posting gets the same message as the eval (job-agent/evals/run_eval.py): profile
and resume from job-agent/context/, plus company, role, location and posting text.

The result goes to approved.json, ready for `job_check.py add approved.json`:
  add           roles to insert in the tracker (link, fit, why + main gap)
  reject        links of roles the model skipped
  needs_review  postings with no usable decision (failed call, invalid reply, or no
                posting text). These are never rejected, so a good job can't be lost:
                `add` leaves them unseen and the next fetch brings them back.

Usage:
  python3.7 scripts/judge_candidates.py
  python3.7 scripts/judge_candidates.py --model anthropic/claude-haiku-5.5
  python3.7 scripts/judge_candidates.py --dry-run   # print decisions; don't write approved.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "job-agent", "evals"))
import llm_client  # noqa: E402
import run_eval  # noqa: E402
import scoring  # noqa: E402

CANDIDATES = os.path.join(ROOT, ".job-check", "candidates.json")
APPROVED = os.path.join(ROOT, "approved.json")
PROMPT = os.path.join(ROOT, "job-agent", "prompts", "judge_v4.md")
DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"


def invalid_reason(out):
    """Return why a parsed reply can't be trusted, or None if it is usable."""
    if not out:
        return "reply was empty or not readable JSON"
    if not scoring.is_valid(out):
        return "reply used a value the prompt doesn't allow"
    if not isinstance(out.get("why"), str) or not out["why"].strip():
        return "reply has no explanation"
    if out["decision"] == "add":
        if out.get("skip_reason") is not None or not out.get("fit") or not out.get("gap_category"):
            return "add decision is missing fit or gap, or also has a skip reason"
        gap = out.get("main_gap")
        if out["gap_category"] != "none" and (not isinstance(gap, str) or not gap.strip()):
            return "add decision doesn't name the main gap"
    elif not out.get("skip_reason") or out.get("fit") is not None or out.get("gap_category") is not None:
        return "skip decision is missing its reason, or also has a fit or gap"
    return None


def why_with_gap(out):
    why = out["why"].strip()
    gap = (out.get("main_gap") or "").strip() if out["gap_category"] != "none" else "none"
    return f"{why} Main gap: {gap}"


def judge_all(candidates, model, system):
    """Return (decisions, total cost). Any failure sends that posting to needs_review."""
    decisions = {"add": [], "reject": [], "needs_review": []}
    total_cost = 0.0
    for i, c in enumerate(candidates, 1):
        label = f"{i}/{len(candidates)} {c['company']} | {c['role']}"

        def review(reason):
            decisions["needs_review"].append({"link": c["link"], "company": c["company"],
                                              "role": c["role"], "reason": reason})
            print(f"REVIEW  {label}: {reason}", flush=True)

        if not (c.get("posting_text") or "").strip():
            review("no posting text was available, so the model was not called")
            continue
        try:
            text, _, cost = llm_client.chat(model, system, run_eval.build_user_message(c))
        except Exception as e:  # a failed call must not reject the posting
            review(f"model call failed: {e}")
            continue
        total_cost += cost or 0
        out = llm_client.parse_json(text)
        problem = invalid_reason(out)
        if problem:
            review(problem)
        elif out["decision"] == "add":
            decisions["add"].append({"link": c["link"], "fit": out["fit"], "why": why_with_gap(out)})
            print(f"ADD     {label}: {out['fit']} fit; gap: {out['gap_category']}", flush=True)
        else:
            decisions["reject"].append(c["link"])
            print(f"SKIP    {label}: {out['skip_reason']}", flush=True)
    return decisions, total_cost


def main(model, dry_run):
    if not os.path.exists(CANDIDATES):
        sys.exit("No candidates file found. Run `python3.7 scripts/job_check.py fetch` first.")
    data = json.load(open(CANDIDATES))
    system = open(PROMPT).read()
    for error in data.get("board_errors", []):
        print(f"Board error from fetch: {error}")
    decisions, cost = judge_all(data["candidates"], model, system)

    print(f"\nModel: {model}")
    print(f"Add: {len(decisions['add'])}  Reject: {len(decisions['reject'])}  "
          f"Needs review: {len(decisions['needs_review'])}  Cost: ${cost:.4f}")
    if decisions["needs_review"]:
        print("\nNeeds review (not rejected; these return on the next fetch):")
        for item in decisions["needs_review"]:
            print(f"  {item['company']} | {item['role']}\n    {item['link']}\n    {item['reason']}")
    if dry_run:
        print("\nDry run: approved.json was not written.")
        return
    approved = dict(decisions, candidates_file=CANDIDATES)
    temp = APPROVED + ".tmp"
    with open(temp, "w") as f:
        json.dump(approved, f, indent=1)
    os.replace(temp, APPROVED)
    print(f"\nWrote {os.path.relpath(APPROVED, ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Judge fetched job postings with prompt v4.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenRouter model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="print decisions without writing approved.json")
    args = parser.parse_args()
    main(args.model, args.dry_run)
