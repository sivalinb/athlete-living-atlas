"""LangGraph orchestration with checkpointed, resumable human-review handoff."""

from typing import TypedDict
from .agent import Investigator
from .safety import normalize


class State(TypedDict, total=False):
    question: str
    result: dict
    review_note: str


def compile_graph(db, checkpointer=None):
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import interrupt

    def validate(state):
        return {"question": normalize(state["question"])}

    def investigate(state):
        agent = Investigator(db)
        try:
            return {"result": agent.ask(state["question"])}
        finally:
            agent.close()

    def human_review(state):
        note = interrupt(
            {
                "status": state["result"]["status"],
                "reason": state["result"].get("reason", "insufficient_evidence"),
                "instruction": "Add a review note. Review does not bypass blocked tools or generate a medical answer.",
            }
        )
        if not isinstance(note, str) or len(note) > 1000:
            raise ValueError("Review note must be a string of at most 1000 characters")
        return {"review_note": note}

    graph = StateGraph(State)
    graph.add_node("validate", validate)
    graph.add_node("investigate", investigate)
    graph.add_node("human_review", human_review)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "investigate")
    graph.add_conditional_edges(
        "investigate",
        lambda state: "done" if state["result"]["status"] == "answered" else "review",
        {"done": END, "review": "human_review"},
    )
    graph.add_edge("human_review", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
