"""Publish reproducible synthetic evaluations and nested execution spans to Braintrust."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid
from ..demo import generate
from ..ingest import ingest
from .agent import Investigator

ROOT = Path(__file__).resolve().parents[2]


def main():
    import braintrust
    from braintrust.git_fields import GitMetadataSettings

    p = argparse.ArgumentParser()
    p.add_argument("--project", default="athlete-observatory")
    p.add_argument(
        "--include-nebius",
        action="store_true",
        help="Also run the 40 public questions with the configured Nebius planner",
    )
    p.add_argument("--report", default=".local/braintrust-evidence.json")
    a = p.parse_args()
    raw = (ROOT / "evals/cases.json").read_bytes()
    cases = json.loads(raw)
    revision = hashlib.sha256(raw).hexdigest()
    dataset = braintrust.init_dataset(
        project=a.project,
        name="investigator-" + revision[:12],
        description="Public synthetic development cases. Assistant-authored labels await user review.",
    )
    ids = {}
    for c in cases:
        ids[c["id"]] = dataset.insert(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, revision + c["id"])),
            input={"question": c["question"], "fail_once": c.get("fail_once", False)},
            expected={
                "route": "review" if c["expected_route"] == "blocked" else c["expected_route"],
                "status": c["expected_status"],
            },
            metadata={"case_id": c["id"], "scenario": c["scenario"], "dataset_sha256": revision},
        )
    dataset.flush()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "project": a.project,
        "dataset_sha256": revision,
        "data_scope": "Only public synthetic fixtures; no personal Health data or raw outputs",
        "experiments": [],
    }
    variants = [("baseline", "local"), ("improved", "local")] + (
        [("improved", "nebius")] if a.include_nebius else []
    )
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "demo.zip"
        db = Path(tmp) / "synthetic.sqlite"
        generate(archive)
        ingest(archive, db)
        for variant, planner in variants:
            name = f"{variant}-{planner}-{stamp}"
            experiment = braintrust.init(
                project=a.project,
                experiment=name,
                dataset=dataset,
                is_public=False,
                git_metadata_settings=GitMetadataSettings(collect="none"),
                metadata={
                    "dataset_sha256": revision,
                    "variant": variant,
                    "planner": planner,
                    "code_version": "investigator-v1",
                },
            )
            agent = Investigator(db, ":memory:", variant=variant, planner=planner)
            outcomes = []
            try:
                for c in cases:
                    expected = {
                        "route": "review" if c["expected_route"] == "blocked" else c["expected_route"],
                        "status": c["expected_status"],
                    }
                    with experiment.start_span(
                        name=c["id"],
                        type="eval",
                        input={"question": c["question"]},
                        expected=expected,
                        dataset_record_id=ids[c["id"]],
                        metadata={"case_id": c["id"], "scenario": c["scenario"]},
                    ) as span:

                        def record_step(step):
                            with span.start_span(
                                name=step["name"],
                                type="tool"
                                if step["name"]
                                in {"retrieve", "training_summary", "latest_workout", "signal_inventory"}
                                else "task",
                                start_time=time.time() - step["latency_ms"] / 1000,
                                metadata={"measured_latency_ms": step["latency_ms"]},
                            ) as child:
                                child.log(output={"status": step["status"]})

                        agent.on_step = record_step
                        result = agent.ask(c["question"], fail_once=c.get("fail_once", False))
                        route_ok = result["route"] == expected["route"]
                        status_ok = result["status"] == expected["status"]
                        fidelity = (
                            result["status"] != "answered"
                            or bool(result["citations"])
                            and set(result["citations"]) <= {e["id"] for e in result["evidence"]}
                        )
                        output = {
                            k: result[k] for k in ["route", "status", "tool_calls", "latency_ms", "version"]
                        }
                        scores = {
                            "route_accuracy": int(route_ok),
                            "status_accuracy": int(status_ok),
                            "citation_validity": int(bool(fidelity)),
                            "case_pass": int(route_ok and status_ok and fidelity),
                        }
                        usage = result.get("usage", {})
                        span.log(
                            output=output,
                            scores=scores,
                            metrics={
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "completion_tokens": usage.get("completion_tokens", 0),
                                "tokens": usage.get("total_tokens", 0),
                            },
                            metadata={
                                "measured_latency_ms": result["latency_ms"],
                                "model_usage_reported": bool(usage),
                            },
                        )
                        outcomes.append(
                            {
                                "case_id": c["id"],
                                **scores,
                                **{k: result[k] for k in ("latency_ms", "tool_calls", "route", "status")},
                                "tokens": usage.get("total_tokens", 0 if planner == "local" else None),
                            }
                        )
                    if len(outcomes) == 1:
                        # Force a first-row write/readback before sending the remaining batch.
                        experiment.flush()
                        if not list(experiment.fetch()):
                            raise RuntimeError("Braintrust first-row readback failed")
                experiment.flush()
                reader = braintrust.init(project=a.project, experiment=name, open=True)
                stored = list(reader.fetch())
                seen = {
                    r.get("metadata", {}).get("case_id")
                    for r in stored
                    if (r.get("input") or {}).get("question")
                }
                if len(seen) != len(cases):
                    raise RuntimeError(f"Braintrust readback incomplete: {len(seen)}/{len(cases)} cases")
                summary = experiment.summarize()
                record = {
                    "name": name,
                    "planner": planner,
                    "variant": variant,
                    "case_count": len(cases),
                    "verified_case_count": len(seen),
                    "pass_rate": sum(x["case_pass"] for x in outcomes) / len(outcomes),
                    "experiment_url": summary.experiment_url,
                    "cases": outcomes,
                }
                report["experiments"].append(record)
                Path(a.report).parent.mkdir(parents=True, exist_ok=True)
                Path(a.report).write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps({k: v for k, v in record.items() if k != "cases"}), flush=True)
            finally:
                agent.close()
    print("Braintrust experiments persisted and read back; no personal health data uploaded.")


if __name__ == "__main__":
    main()
