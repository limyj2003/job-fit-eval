"""Score agent outputs against the labeled answers in data/labels.csv.

Each output is a dict like:
  {"decision": "add", "skip_reason": None, "fit": "medium", "gap_category": "years", ...}

Scores per scenario (1 = correct, 0 = wrong, None = not applicable):
  valid           output was parseable JSON with allowed values
  decision        add/skip matches the label
  fit_exact       fit matches the label (added roles only)
  fit_within_one  fit is at most one level off (added roles only)
  gap             gap_category matches the label (added roles only)
  skip_reason     skip_reason matches the label (skipped roles only)

The summary also reports precision and recall for the "add" decision, and the
false-skip count: postings labeled add that the model did not add.
"""
import csv
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(HERE, "data", "labels.csv")

ALLOWED = {
    "decision": {"add", "skip"},
    "skip_reason": {"sales", "too_senior", "stem_degree", "coding_required", "location", None},
    "fit": {"high", "medium", "low", None},
    "gap_category": {"years", "python", "grad_window", "stem_degree", "domain", "none", None},
}
FIT_LEVEL = {"low": 0, "medium": 1, "high": 2}


def load_labels():
    return {r["id"]: r for r in csv.DictReader(open(LABELS))}


def is_valid(out):
    if not isinstance(out, dict):
        return False
    for key, allowed in ALLOWED.items():
        if out.get(key) not in allowed:
            return False
    return True


def score_one(label, out):
    s = {"valid": int(is_valid(out)), "decision": 0, "fit_exact": None, "fit_within_one": None,
         "gap": None, "skip_reason": None}
    out = out if isinstance(out, dict) else {}
    s["decision"] = int(out.get("decision") == label["expected_decision"])
    if label["expected_decision"] == "add":
        fit = out.get("fit")
        s["fit_exact"] = int(fit == label["expected_fit"])
        s["fit_within_one"] = int(fit in FIT_LEVEL and abs(FIT_LEVEL[fit] - FIT_LEVEL[label["expected_fit"]]) <= 1)
        s["gap"] = int(out.get("gap_category") == label["expected_gap"])
    else:
        s["skip_reason"] = int(out.get("skip_reason") == label["skip_reason"])
    return s


def summarize(rows):
    """rows: list of dicts with 'scores', 'label', 'out', optional 'seconds' and 'cost'."""
    def avg(key):
        vals = [r["scores"][key] for r in rows if r["scores"][key] is not None]
        return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)

    adds = [r for r in rows if r["label"]["expected_decision"] == "add"]
    pred_adds = [r for r in rows if r["out"].get("decision") == "add"]
    true_pos = [r for r in adds if r["out"].get("decision") == "add"]
    summary = {k: avg(k) for k in ("valid", "decision", "fit_exact", "fit_within_one", "gap", "skip_reason")}
    summary["add_precision"] = (len(true_pos) / len(pred_adds), len(pred_adds)) if pred_adds else (None, 0)
    summary["add_recall"] = (len(true_pos) / len(adds), len(adds)) if adds else (None, 0)
    # False skips: labeled add, but the model did not add it (skipped, or gave no usable answer).
    # These are the good jobs that would never reach the tracker.
    summary["false_skips"] = len(adds) - len(true_pos)
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    costs = [r["cost"] for r in rows if r.get("cost") is not None]
    summary["avg_seconds"] = sum(secs) / len(secs) if secs else None
    summary["total_cost_usd"] = sum(costs) if costs else None
    return summary


LABELS_TEXT = {
    "decision": "Decision accuracy (add vs skip)",
    "add_precision": "Of roles it added, % that should be added",
    "add_recall": "Of roles that should be added, % it added",
    "fit_exact": "Fit rating exactly right",
    "fit_within_one": "Fit rating within one level",
    "gap": "Main gap category right",
    "skip_reason": "Skip reason right",
    "valid": "Valid output format",
}


def print_summary(name, summary):
    print(f"\n=== {name} ===")
    for key, text in LABELS_TEXT.items():
        val, n = summary[key]
        shown = "n/a" if val is None else f"{val * 100:5.1f}%"
        extra = ""
        if key == "add_recall" and "false_skips" in summary:
            extra = f"  false skips: {summary['false_skips']}"
        print(f"  {text:<45} {shown}  (n={n}){extra}")
    if summary["avg_seconds"] is not None:
        print(f"  {'Average seconds per posting':<45} {summary['avg_seconds']:5.1f}")
    if summary["total_cost_usd"] is not None:
        print(f"  {'Total cost (USD)':<45} ${summary['total_cost_usd']:.4f}")
