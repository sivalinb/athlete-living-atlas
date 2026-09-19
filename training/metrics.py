"""Comparable per-label precision/recall/F1, confusion matrix and accuracy."""

from .prepare import LABELS


def metrics(truth, predictions):
    if len(truth) != len(predictions) or not truth:
        raise ValueError("Nonempty, equally sized labels required")
    columns = LABELS + ["invalid"]
    matrix = [[0] * len(columns) for _ in LABELS]
    for y, p in zip(truth, predictions):
        matrix[LABELS.index(y)][columns.index(p) if p in LABELS else -1] += 1
    per_class = {}
    for i, label in enumerate(LABELS):
        tp = matrix[i][i]
        support = sum(matrix[i])
        pred = sum(row[i] for row in matrix)
        precision = tp / pred if pred else 0
        recall = tp / support if support else 0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
            "support": support,
        }
    return {
        "accuracy": sum(y == p for y, p in zip(truth, predictions)) / len(truth),
        "macro_f1": sum(r["f1"] for r in per_class.values()) / len(LABELS),
        "per_class": per_class,
        "row_labels": LABELS,
        "column_labels": columns,
        "confusion_matrix": matrix,
    }
