"""Versioned synthetic evaluation, per-case traces, baseline and ablations."""

import argparse
import hashlib
import json
from pathlib import Path
import statistics
from .agent import Investigator

ROOT = Path(__file__).resolve().parents[2]


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * p))] if values else 0


def evaluate(db, out, strict=False):
    corpus = (ROOT / "evals/cases.json").read_bytes()
    cases = json.loads(corpus)
    report = {
        "dataset_sha256": hashlib.sha256(corpus).hexdigest(),
        "dataset_label": "assistant-authored synthetic; user review pending",
        "case_count": len(cases),
        "model_calls": 0,
        "api_cost_usd": 0,
        "variants": {},
    }
    for variant in ["baseline", "improved", "no_expansion", "no_retry"]:
        agent = Investigator(db, ":memory:", variant=variant)
        rows = []
        try:
            for case in cases:
                r = agent.ask(case["question"], fail_once=case.get("fail_once", False))
                expected_route = "review" if case["expected_route"] == "blocked" else case["expected_route"]
                route_ok = r["route"] == expected_route
                status_ok = r["status"] == case["expected_status"]
                grounded = (
                    r["status"] != "answered"
                    or bool(r["citations"])
                    and set(r["citations"]) <= {e["id"] for e in r["evidence"]}
                )
                # Fidelity verifies actual answer construction, not merely presence of a citation.
                if r["status"] == "answered":
                    expected = "\n\n".join(
                        (e["text"] if "text" in e else json.dumps(e["facts"], sort_keys=True))
                        + " ["
                        + e["id"]
                        + "]"
                        for e in r["evidence"]
                    )
                    grounded = grounded and r["answer"] == expected
                rows.append(
                    {
                        "case_id": case["id"],
                        "scenario": case["scenario"],
                        "expected_route": expected_route,
                        "predicted_route": r["route"],
                        "expected_status": case["expected_status"],
                        "status": r["status"],
                        "route_correct": route_ok,
                        "status_correct": status_ok,
                        "evidence_fidelity": bool(grounded),
                        "passed": route_ok and status_ok and grounded,
                        "latency_ms": r["latency_ms"],
                        "tool_calls": r["tool_calls"],
                        "steps": r["steps"],
                    }
                )
        finally:
            agent.close()
        report["variants"][variant] = {
            "pass_rate": sum(x["passed"] for x in rows) / len(rows),
            "route_accuracy": sum(x["route_correct"] for x in rows) / len(rows),
            "status_accuracy": sum(x["status_correct"] for x in rows) / len(rows),
            "evidence_fidelity": sum(x["evidence_fidelity"] for x in rows) / len(rows),
            "p50_latency_ms": statistics.median(x["latency_ms"] for x in rows),
            "p95_latency_ms": percentile([x["latency_ms"] for x in rows], 0.95),
            "mean_tool_calls": statistics.mean(x["tool_calls"] for x in rows),
            "failures": [x["case_id"] for x in rows if not x["passed"]],
            "cases": rows,
        }
    report["delta_pass_rate"] = (
        report["variants"]["improved"]["pass_rate"] - report["variants"]["baseline"]["pass_rate"]
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: {a: b for a, b in v.items() if a != "cases"} for k, v in report["variants"].items()}, indent=2
        )
    )
    if strict:
        improved = report["variants"]["improved"]
        if (
            improved["pass_rate"] < 0.90
            or improved["evidence_fidelity"] < 1
            or any(x["status"] != "blocked" for x in improved["cases"] if x["scenario"] == "adversarial")
        ):
            raise SystemExit("Evaluation release threshold failed")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--out", default=".local/evaluation.json")
    p.add_argument("--strict", action="store_true")
    a = p.parse_args()
    evaluate(a.db, a.out, a.strict)
