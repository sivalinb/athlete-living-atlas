"""Build a synthetic routing corpus; split semantic families, never paraphrases across folds."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

LABELS = ["training_summary", "latest_workout", "signal_inventory", "knowledge", "review"]
FAMILIES = {
    "training_summary": [
        "training totals",
        "recorded session count",
        "aggregate distance",
        "active hours",
        "weekly volume",
        "exercise summary",
        "total kilometres",
        "training overview",
        "activity totals",
        "distance across sessions",
    ],
    "latest_workout": [
        "latest outdoor run",
        "stops in my recent run",
        "last outing",
        "recent workout elapsed time",
        "most recent running session",
        "last run active time",
        "latest run pause events",
        "last workout coverage",
        "recent burro run",
        "recent race stop candidates",
    ],
    "signal_inventory": [
        "available sensors",
        "missing measurements",
        "signal inventory",
        "recording sources",
        "device coverage",
        "sampling cadence",
        "blank readings",
        "sensor availability",
        "recorded metric types",
        "measurement counts",
    ],
    "knowledge": [
        "meaning of SDNN",
        "difference between HRV metrics",
        "sleep overlap rules",
        "route coverage definition",
        "GPS gap handling rules",
        "import refresh procedure",
        "device comparison limitations",
        "privacy publication policy",
        "pause versus low motion definition",
        "dashboard deployment procedure",
    ],
    "review": [
        "race winner prediction",
        "medical diagnosis request",
        "treatment recommendation",
        "motivation of a burro",
        "unavailable future results",
        "personal medication advice",
        "home location request",
        "destructive database change",
        "private data publication request",
        "unsupported astronomy question",
    ],
}
PREFIXES = [
    "Explain the routing intent for: ",
    "Classify this dashboard question: ",
    "Help with ",
    "I want information about ",
]


def dataset():
    rows = []
    for label, families in FAMILIES.items():
        order = list(range(len(families)))
        random.Random(42).shuffle(order)
        held = set(order[:2])
        for i, family in enumerate(families):
            for prefix in PREFIXES:
                question = prefix + family
                rows.append(
                    {
                        "id": hashlib.sha256(question.encode()).hexdigest()[:16],
                        "question": question,
                        "label": label,
                        "group": label + ":" + str(i),
                        "split": "validation" if i in held else "train",
                    }
                )
    return rows


def prepare(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = dataset()
    info = {}
    groups = defaultdict(set)
    for split in ["train", "validation"]:
        selected = [r for r in rows if r["split"] == split]
        groups[split] = {r["group"] for r in selected}
        converted = [
            {
                "conversations": [
                    {"from": "human", "value": prompt(r["question"])},
                    {"from": "gpt", "value": r["label"]},
                ]
            }
            for r in selected
        ]
        (out / (split + ".json")).write_text(json.dumps(converted, indent=2) + "\n")
        (out / (split + "-labels.json")).write_text(json.dumps(selected, indent=2) + "\n")
        info["athlete_" + split] = {
            "file_name": split + ".json",
            "formatting": "sharegpt",
            "columns": {"messages": "conversations"},
            "tags": {"role_tag": "from", "content_tag": "value", "user_tag": "human", "assistant_tag": "gpt"},
        }
    assert not groups["train"] & groups["validation"]
    (out / "dataset_info.json").write_text(json.dumps(info, indent=2) + "\n")
    manifest = {
        "source": "fully synthetic assistant-authored routing examples; human review pending",
        "rows": len(rows),
        "train": sum(r["split"] == "train" for r in rows),
        "validation": sum(r["split"] == "validation" for r in rows),
        "split": "stratified 80/20 semantic-family holdout, seed 42",
        "sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def prompt(question):
    return (
        "Choose exactly one routing label: "
        + ", ".join(LABELS)
        + ". Return only the label.\nQuestion: "
        + question
        + "\nLabel:"
    )


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--out", default=".local/training")
    a = p.parse_args()
    print(json.dumps(prepare(a.out), indent=2))
