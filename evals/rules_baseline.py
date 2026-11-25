"""Version 0: a no-AI baseline that judges postings with keyword rules only.

This is the "is AI even needed?" comparison point. It uses the same kind of
title/location/years filters as the daily job check script, plus simple
keyword checks for STEM degrees and coding.
"""
import re

BAY = re.compile(r"san francisco|\bsf\b|bay area|palo alto|mountain view|menlo park|redwood city|san mateo|"
                 r"oakland|berkeley|san jose|sunnyvale|santa clara", re.I)
SALES_TITLE = re.compile(r"sales|account exec|account associate|\bsdr\b|\bbdr\b|growth associate|gtm associate|"
                         r"development strategist", re.I)
STEM_REQ = re.compile(r"(stem|computer science|engineering|technical) degree", re.I)
CODING_REQ = re.compile(r"strong coding|ml engineering|software engineering experience|unit tests", re.I)
YEARS = re.compile(r"(\d+)\s*\+?\s*(?:-|–|to)?\s*(\d+)?\s*\+?\s*years", re.I)
TARGET = re.compile(r"operations associate|strategic project|ai operations|strategist, agent", re.I)


def min_years(text):
    """Smallest 'N years' requirement mentioned, ignoring benefits like '4 years vesting'."""
    found = []
    for m in YEARS.finditer(text):
        window = text[max(0, m.start() - 40): m.end() + 40].lower()
        if any(w in window for w in ("vest", "founded", "spent", "ago", "old")):
            continue
        found.append(int(m.group(1)))
    return min(found) if found else None


def judge(scenario):
    title, text, loc = scenario["role"], scenario["posting_text"], scenario["location"]
    yrs = min_years(text)
    if not BAY.search(loc):
        return {"decision": "skip", "skip_reason": "location"}
    if SALES_TITLE.search(title):
        return {"decision": "skip", "skip_reason": "sales"}
    if CODING_REQ.search(text):
        return {"decision": "skip", "skip_reason": "coding_required"}
    if STEM_REQ.search(text) and "econom" not in text.lower():
        return {"decision": "skip", "skip_reason": "stem_degree"}
    if yrs is not None and yrs >= 4:
        return {"decision": "skip", "skip_reason": "too_senior"}
    if TARGET.search(title) and (yrs is None or yrs <= 2):
        fit = "high"
    elif yrs is not None and yrs >= 3:
        fit = "medium"
    else:
        fit = "medium"
    gap = "years" if yrs else "none"
    if re.search(r"\bpython\b|typescript|\bgit\b", text, re.I):
        gap = "python" if yrs is None or yrs <= 1 else gap
    return {"decision": "add", "skip_reason": None, "fit": fit, "gap_category": gap,
            "main_gap": None, "why": "keyword rules"}
