"""Fifteen explicit method questions; compare chunking and retrieval with known source sections."""

import argparse
import json
from pathlib import Path
from .rag import Index

QUESTIONS = [
    ("How is workout distance calculated?", "training-volume"),
    ("What is the GPS stop threshold?", "stops-and-pauses"),
    ("How are missing GPS intervals handled?", "stops-and-pauses"),
    ("What does route coverage measure?", "route-coverage"),
    ("How do SDNN and RMSSD differ?", "heart-rate-variability"),
    ("How are overlapping sleep intervals handled?", "sleep-measurement"),
    ("What boundary assigns sleep to a night?", "sleep-measurement"),
    ("Why can changing devices affect measurements?", "device-changes"),
    ("How do I import a fresh Apple Health export?", "import-and-refresh"),
    ("Does importing append duplicate history?", "import-and-refresh"),
    ("What should I inspect before comparing performance?", "data-quality"),
    ("What context matters when comparing races?", "race-comparisons"),
    ("Which screenshot is authorized for publication?", "privacy-and-publication"),
    ("Can this application prescribe treatment?", "ai-boundaries"),
    ("How are Grafana definitions deployed?", "deployment"),
]


def evaluate(out):
    report = {
        "source": "assistant-authored method questions; expected source sections explicitly specified",
        "cases": len(QUESTIONS),
        "variants": {},
    }
    for strategy in ["section", "fixed"]:
        index = Index(strategy=strategy)
        try:
            for mode in ["bm25", "vector", "hybrid"]:
                rows = []
                for q, expected in QUESTIONS:
                    hits = index.search(q, mode=mode)
                    rank = next(
                        (i + 1 for i, h in enumerate(hits) if h["id"].startswith("kb:" + expected + ":")),
                        None,
                    )
                    rows.append(
                        {
                            "question": q,
                            "expected_section": expected,
                            "rank": rank,
                            "retrieved": [h["id"] for h in hits],
                        }
                    )
                report["variants"][strategy + "-" + mode] = {
                    "hit_at_3": sum(r["rank"] is not None for r in rows) / len(rows),
                    "mrr_at_3": sum(1 / r["rank"] if r["rank"] else 0 for r in rows) / len(rows),
                    "rows": rows,
                }
        finally:
            index.close()
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: {m: v for m, v in r.items() if m != "rows"} for k, r in report["variants"].items()}, indent=2
        )
    )
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=".local/retrieval-evaluation.json")
    a = p.parse_args()
    evaluate(a.out)
