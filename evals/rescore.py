"""Re-score saved runs against the current labels, without calling any model again.

Use this after fixing labels: the model's answers are unchanged, only the answer key moved.
Usage: python3 evals/rescore.py results/<file>.jsonl [more files...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring  # noqa: E402

labels = scoring.load_labels()
for path in sys.argv[1:]:
    lines = open(path).read().splitlines()
    head, rows = json.loads(lines[0]), [json.loads(l) for l in lines[1:]]
    for r in rows:
        r["label"] = labels[r["id"]]
        r["scores"] = scoring.score_one(r["label"], r["out"])
    summary = scoring.summarize(rows)
    scoring.print_summary(f"{head['model']} (prompt {head['prompt']}) — rescored", summary)
    wrong = [r for r in rows if not r["scores"]["decision"]]
    for r in wrong:
        exp = r["label"]["expected_decision"] + "/" + (r["label"]["expected_fit"] or r["label"]["skip_reason"])
        got = f"{r['out'].get('decision')}/{r['out'].get('fit') or r['out'].get('skip_reason')}"
        print(f"  wrong: {r['id']} {r['company']} | {r['role'][:45]}: expected {exp}, got {got}")
    head["summary"] = summary
    head["rescored_with_labels"] = "current"
    with open(path, "w") as f:
        f.write(json.dumps(head) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
