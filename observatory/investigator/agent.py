"""Bounded plan/execute/verify workflow with persistent local trace evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid
from .rag import Index
from .safety import input_policy, normalize
from .tools import HealthTools

VERSION = "investigator-v1"


def route(question, improved=True):
    q = question.lower()
    if improved and re.search(r"thinking|motivation|favorite|winner", q):
        return "review"
    if improved and re.search(r"how (many|much)|count|aggregate", q):
        return "training_summary"
    if re.search(r"\b(explain|define|meaning|how|why|what is|what are|difference|rule|threshold)\b", q):
        return "knowledge"
    if re.search(r"latest|last run|recent run|workout|stop|pause", q):
        return "latest_workout"
    if re.search(r"total|summary|training|volume|distance|sessions|hours", q):
        return "training_summary"
    if re.search(r"coverage|missing|source|device|inventory|signal", q):
        return "signal_inventory"
    if improved:
        if re.search(r"outing|halt|burro|slow moment", q):
            return "latest_workout"
        if re.search(r"aggregate|count|kilomet|time spent|overview", q):
            return "training_summary"
        if re.search(r"blank|holes|watch|cadence|available|sensor", q):
            return "signal_inventory"
        if re.search(r"sdnn|rmssd|hrv|sleep|import|export|refresh|privacy|deploy|comparison", q):
            return "knowledge"
    return "review"


class Investigator:
    def __init__(self, db, trace_db=".local/investigator.sqlite", variant="improved", planner="local"):
        if variant not in {"baseline", "improved", "no_expansion", "no_retry"}:
            raise ValueError("Unknown experiment variant")
        if planner not in {"local", "nebius", "qwen"}:
            raise ValueError("Unknown planner")
        self.on_step = None
        self.tools = HealthTools(db)
        self.index = Index()
        self.variant, self.planner = variant, planner
        if trace_db != ":memory:":
            Path(trace_db).parent.mkdir(parents=True, exist_ok=True)
        self.trace = sqlite3.connect(trace_db)
        self.trace.executescript("""CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,started TEXT,version TEXT,variant TEXT,status TEXT,route TEXT,latency_ms REAL,tool_calls INTEGER,question_sha TEXT,result_json TEXT);
        CREATE TABLE IF NOT EXISTS steps(run_id TEXT,ordinal INTEGER,name TEXT,status TEXT,latency_ms REAL,PRIMARY KEY(run_id,ordinal));""")
        self.trace.commit()
        if trace_db != ":memory:":
            Path(trace_db).chmod(0o600)

    def close(self):
        self.tools.close()
        self.index.close()
        self.trace.close()

    def ask(self, question, days=180, fail_once=False):
        started = time.perf_counter()
        question = normalize(question)
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("Window must be 1–366 days")
        run_id = uuid.uuid4().hex
        steps = []

        def mark(name, status="ok", latency=0):
            steps.append({"name": name, "status": status, "latency_ms": round(latency, 3)})
            if self.on_step:
                self.on_step(steps[-1])

        result = {
            "run_id": run_id,
            "status": "review",
            "route": "review",
            "answer": "No supported evidence was found. Human review is required.",
            "evidence": [],
            "citations": [],
            "tool_calls": 0,
            "usage": {},
            "planner": self.planner,
            "version": VERSION,
            "corpus_revision": self.index.revision,
        }
        policy_start = time.perf_counter()
        reason = input_policy(question)
        mark("input_policy", "blocked" if reason else "ok", (time.perf_counter() - policy_start) * 1000)
        if reason:
            result.update(
                status="blocked",
                reason=reason,
                answer="This request is outside the investigator's read-only observational scope.",
            )
        else:
            plan_start = time.perf_counter()
            selected = route(question, self.variant != "baseline")
            if self.planner == "nebius":
                from .provider import plan

                try:
                    selected, result["usage"] = plan(question)
                except Exception:
                    selected = "review"
                    result["reason"] = "provider_unavailable_or_invalid"
            if self.planner == "qwen":
                from .local_model import classify

                try:
                    selected = classify(
                        question, os.environ.get("ATHLETE_ROUTER_DIR", ".local/qwen-router/merged")
                    )
                except Exception:
                    selected = "review"
                    result["reason"] = "local_model_unavailable"
            result["route"] = selected
            mark("plan", latency=(time.perf_counter() - plan_start) * 1000)
            if selected == "knowledge":
                start = time.perf_counter()
                found = self.index.search(
                    question,
                    mode="bm25" if self.variant == "baseline" else "hybrid",
                    top_k=1 if self.variant == "baseline" else 3,
                    expand=self.variant not in {"baseline", "no_expansion"},
                )
                result["tool_calls"] += 1
                mark("retrieve", "ok", (time.perf_counter() - start) * 1000)
                # Reject weak isolated matches, but accept exact title vocabulary.
                useful = [
                    c
                    for c in found
                    if c["overlap"] >= 2
                    or (
                        self.variant != "baseline"
                        and set(c["title"].lower().split()) & set(question.lower().split())
                    )
                    or any(w in question.lower() for w in ("sdnn", "rmssd", "hrv"))
                ]
                if useful:
                    result.update(
                        status="answered",
                        evidence=useful,
                        answer="\n\n".join(c["text"] + " [" + c["id"] + "]" for c in useful),
                        citations=[c["id"] for c in useful],
                    )
            elif selected in {"training_summary", "latest_workout", "signal_inventory"}:
                attempts = 2 if self.variant not in {"baseline", "no_retry"} else 1
                for attempt in range(attempts):
                    start = time.perf_counter()
                    result["tool_calls"] += 1
                    try:
                        if fail_once and attempt == 0:
                            raise sqlite3.OperationalError("injected transient failure")
                        evidence = self.tools.run(selected, days)
                        mark(selected, "ok", (time.perf_counter() - start) * 1000)
                        if evidence["facts"]:
                            result.update(
                                status="answered",
                                evidence=[evidence],
                                citations=[evidence["id"]],
                                answer=json.dumps(evidence["facts"], sort_keys=True)
                                + " ["
                                + evidence["id"]
                                + "]",
                            )
                        break
                    except sqlite3.OperationalError:
                        mark(
                            selected,
                            "retry" if attempt + 1 < attempts else "failed",
                            (time.perf_counter() - start) * 1000,
                        )
                        result["reason"] = "tool_unavailable"
            verify_start = time.perf_counter()
            if result["status"] == "answered":
                known = {e["id"] for e in result["evidence"]}
                if not result["citations"] or set(result["citations"]) - known:
                    raise AssertionError("Ungrounded response")
                result.pop("reason", None)
            else:
                result["route"] = "review"
                mark("human_review", "required")
            mark("verify", latency=(time.perf_counter() - verify_start) * 1000)
        result["steps"] = steps
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        # Local persistence only. No question text, coordinates, or credentials in trace storage.
        stored = {k: v for k, v in result.items() if k not in {"answer", "evidence"}}
        self.trace.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                datetime.now(timezone.utc).isoformat(),
                VERSION,
                self.variant,
                result["status"],
                result["route"],
                result["latency_ms"],
                result["tool_calls"],
                hashlib.sha256(question.encode()).hexdigest(),
                json.dumps(stored),
            ),
        )
        self.trace.executemany(
            "INSERT INTO steps VALUES(?,?,?,?,?)",
            [(run_id, i, s["name"], s["status"], s["latency_ms"]) for i, s in enumerate(steps)],
        )
        self.trace.commit()
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--db", required=True)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--trace-db", default=".local/investigator.sqlite")
    p.add_argument("--planner", choices=["local", "nebius", "qwen"], default="local")
    a = p.parse_args()
    agent = Investigator(a.db, a.trace_db, planner=a.planner)
    try:
        print(json.dumps(agent.ask(a.question, a.days), indent=2))
    finally:
        agent.close()


if __name__ == "__main__":
    main()
