"""Cheap multinomial Naive Bayes routing baseline. This is not LLM fine-tuning."""

from collections import Counter
import json
import math
from pathlib import Path
from .prepare import dataset, LABELS
from .metrics import metrics
from observatory.investigator.rag import tokens


def train(out):
    rows = dataset()
    counts = {label: Counter() for label in LABELS}
    vocab = set()
    for r in rows:
        if r["split"] == "train":
            words = tokens(r["question"])
            counts[r["label"]].update(words)
            vocab.update(words)

    def classify(q):
        return max(
            LABELS,
            key=lambda label: sum(
                math.log((counts[label][w] + 1) / (sum(counts[label].values()) + len(vocab)))
                for w in tokens(q)
                if w in vocab
            ),
        )

    valid = [r for r in rows if r["split"] == "validation"]
    prediction = [classify(r["question"]) for r in valid]
    report = {
        "method": "multinomial naive Bayes lexical baseline; not LoRA or LLM fine-tuning",
        "validation_count": len(valid),
        **metrics([r["label"] for r in valid], prediction),
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--out", default=".local/router-reference.json")
    a = p.parse_args()
    print(json.dumps(train(a.out), indent=2))
