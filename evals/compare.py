"""Compare two saved runs posting by posting on the add/skip decision.

Lists which postings were FIXED (wrong in the first run, right in the second)
and which REGRESSED (right in the first run, wrong in the second), with company
and role. Both runs are graded against the current labels in data/labels.csv,
so the comparison is fair even if one file was saved before a label fix.

Usage:
  python3 evals/compare.py results/<before>.jsonl results/<after>.jsonl
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring  # noqa: E402


def load_run(path):
    """Return (header, {posting id: record}) from a results file."""
    lines = open(path).read().splitlines()
    return json.loads(lines[0]), {r["id"]: r for r in (json.loads(l) for l in lines[1:])}


def describe(out):
    """Short text for a model answer, e.g. 'add/medium' or 'skip/too_senior'."""
    if not out or not out.get("decision"):
        return "no answer"
    return f"{out['decision']}/{out.get('fit') or out.get('skip_reason') or '?'}"


def name(header):
    return "rules (no AI)" if header["model"] == "rules" else f"{header['model']} prompt {header['prompt']}"


def main(path_a, path_b):
    labels = scoring.load_labels()
    head_a, run_a = load_run(path_a)
    head_b, run_b = load_run(path_b)
    shared = [i for i in labels if i in run_a and i in run_b]
    missing = sorted(set(labels) - set(shared))

    fixed, regressed, still_wrong = [], [], []
    for i in shared:
        label = labels[i]
        right_a = run_a[i]["out"].get("decision") == label["expected_decision"]
        right_b = run_b[i]["out"].get("decision") == label["expected_decision"]
        expected = label["expected_decision"] + "/" + (label["expected_fit"] or label["skip_reason"])
        row = (i, run_b[i]["company"], run_b[i]["role"], expected, describe(run_a[i]["out"]), describe(run_b[i]["out"]))
        if not right_a and right_b:
            fixed.append(row)
        elif right_a and not right_b:
            regressed.append(row)
        elif not right_a and not right_b:
            still_wrong.append(row)

    print(f"A: {name(head_a)}  ({os.path.basename(path_a)})")
    print(f"B: {name(head_b)}  ({os.path.basename(path_b)})")
    print(f"Compared {len(shared)} postings on the add/skip decision, using the current labels.")
    if missing:
        print(f"Not in both files (skipped): {', '.join(missing)}")

    acc_a = sum(run_a[i]["out"].get("decision") == labels[i]["expected_decision"] for i in shared)
    acc_b = sum(run_b[i]["out"].get("decision") == labels[i]["expected_decision"] for i in shared)
    print(f"Correct decisions: A {acc_a}/{len(shared)}  ->  B {acc_b}/{len(shared)}")

    for title, rows in (("FIXED (wrong in A, right in B)", fixed),
                        ("REGRESSED (right in A, wrong in B)", regressed),
                        ("STILL WRONG in both", still_wrong)):
        print(f"\n{title}: {len(rows)}")
        for i, company, role, expected, got_a, got_b in rows:
            print(f"  {i} {company} | {role[:55]}")
            print(f"      expected {expected}; A said {got_a}; B said {got_b}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
