"""Evaluate published synthetic cases in LangSmith; no private DB results are uploaded."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import uuid
from datetime import datetime, timezone
from .agent import Investigator
from ..demo import generate
from ..ingest import ingest


def main():
    from langsmith import Client, traceable

    p = argparse.ArgumentParser()
    p.add_argument("--project", default="athlete-observatory-course")
    a = p.parse_args()
    raw = (Path(__file__).resolve().parents[2] / "evals/cases.json").read_bytes()
    cases = json.loads(raw)
    revision = hashlib.sha256(raw).hexdigest()[:12]
    client = Client(auto_batch_tracing=False)
    # Fail before an evaluation batch if the account cannot persist a single trace.
    probe = uuid.uuid4()
    client.create_run(
        name="athlete-synthetic-preflight",
        run_type="chain",
        id=probe,
        inputs={"fixture": "public-synthetic"},
        outputs={"status": "preflight"},
        end_time=datetime.now(timezone.utc),
        project_name=a.project + "-preflight",
    )
    client.read_run(probe)
    name = "athlete-investigator-" + revision
    if client.has_dataset(dataset_name=name):
        dataset = client.read_dataset(dataset_name=name)
    else:
        dataset = client.create_dataset(
            dataset_name=name, description="Synthetic questions. Assistant labels await user review."
        )
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {
                    "inputs": {"question": c["question"], "fail_once": c.get("fail_once", False)},
                    "outputs": {
                        "route": "review" if c["expected_route"] == "blocked" else c["expected_route"],
                        "status": c["expected_status"],
                    },
                    "metadata": {"case_id": c["id"], "scenario": c["scenario"]},
                }
                for c in cases
            ],
        )
    # Generate a fresh fictional database; caller cannot pass a personal database.
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "synthetic.sqlite"
        archive = Path(tmp) / "synthetic.zip"
        generate(archive)
        ingest(archive, db)
        for variant in ("baseline", "improved"):
            agent = Investigator(db, ":memory:", variant=variant)

            @traceable(name="investigator", run_type="chain")
            def target(inputs):
                result = agent.ask(inputs["question"], fail_once=inputs.get("fail_once", False))
                # Child spans contain only public stage names and status, no health values.
                for step in result["steps"]:

                    @traceable(
                        name=step["name"],
                        run_type="tool"
                        if step["name"]
                        in {"retrieve", "training_summary", "latest_workout", "signal_inventory"}
                        else "chain",
                    )
                    def recorded_step():
                        return {"status": step["status"], "measured_latency_ms": step["latency_ms"]}

                    recorded_step()
                return {k: result[k] for k in ["route", "status", "latency_ms", "tool_calls", "version"]}

            def correctness(outputs, reference_outputs):
                return {
                    "key": "route_and_status",
                    "score": int(
                        outputs["route"] == reference_outputs["route"]
                        and outputs["status"] == reference_outputs["status"]
                    ),
                }

            try:
                client.evaluate(
                    target,
                    data=dataset.name,
                    evaluators=[correctness],
                    experiment_prefix=a.project + "-" + variant,
                    metadata={
                        "dataset_version": revision,
                        "prompt_version": "investigator-v1",
                        "variant": variant,
                    },
                    max_concurrency=0,
                )
            finally:
                agent.close()
    print("Synthetic LangSmith evaluations submitted. Inspect the experiment links emitted by the SDK.")


if __name__ == "__main__":
    main()
