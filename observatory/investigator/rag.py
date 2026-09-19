"""Persistent BM25 + hashed vector retrieval; local vectors are lexical, not neural."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

CORPUS = Path(__file__).resolve().parents[2] / "knowledge/measurement-guide.md"
STOP = set("a an the is are and or of to for in my me what how does do can with it this i".split())
ALIASES = {
    "hrv": "heart rate variability",
    "halt": "stop pause",
    "halts": "stops pauses",
    "donkey": "burro",
    "refresh": "import export",
    "blank": "missing",
    "holes": "missing gaps",
    "rest": "sleep",
    "watch": "device hardware",
    "climbing": "ascent elevation",
}


def tokens(text, expand=True):
    words = re.findall(r"[a-z0-9]+", text.lower())
    if expand:
        words += [w for term in words for w in ALIASES.get(term, "").split()]
    return [w for w in words if w not in STOP]


def vector(words, dim=128):
    v = [0.0] * dim
    for token, n in Counter(words).items():
        digest = hashlib.sha256(token.encode()).digest()
        v[int.from_bytes(digest[:4], "big") % dim] += n * (1 if digest[4] % 2 else -1)
    norm = math.sqrt(sum(x * x for x in v)) or 1
    return [x / norm for x in v]


def chunks(text, strategy="section", size=24):
    result = []
    for section in text.split("\n# "):
        title, _, body = section.lstrip("# ").partition("\n")
        key = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        words = body.split()
        blocks = (
            [body.strip()]
            if strategy == "section"
            else [" ".join(words[i : i + size]) for i in range(0, len(words), size)]
        )
        for i, body in enumerate(blocks):
            result.append(
                {
                    "id": f"kb:{key}:{i}",
                    "title": title,
                    "text": body,
                    "source": "knowledge/measurement-guide.md#" + key,
                }
            )
    return result


class Index:
    def __init__(self, path=":memory:", strategy="section"):
        if strategy not in {"section", "fixed"}:
            raise ValueError("Unsupported chunk strategy")
        text = CORPUS.read_text()
        self.revision = hashlib.sha256((strategy + text).encode()).hexdigest()
        self.con = sqlite3.connect(path)
        self.con.execute("CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, payload TEXT, vector TEXT)")
        self.con.execute("CREATE TABLE IF NOT EXISTS revision(value TEXT)")
        old = self.con.execute("SELECT value FROM revision").fetchone()
        if not old or old[0] != self.revision:
            self.con.execute("DELETE FROM chunks")
            self.con.execute("DELETE FROM revision")
            for c in chunks(text, strategy):
                self.con.execute(
                    "INSERT INTO chunks VALUES(?,?,?)",
                    (c["id"], json.dumps(c), json.dumps(vector(tokens(c["title"] + " " + c["text"])))),
                )
            self.con.execute("INSERT INTO revision VALUES(?)", (self.revision,))
            self.con.commit()
        self.rows = [
            (json.loads(p), json.loads(v))
            for p, v in self.con.execute("SELECT payload,vector FROM chunks ORDER BY id")
        ]

    def close(self):
        self.con.close()

    def search(self, question, mode="hybrid", top_k=3, expand=True):
        if mode not in {"bm25", "vector", "hybrid"} or not 1 <= top_k <= 5:
            raise ValueError("Invalid retrieval configuration")
        q = tokens(question, expand)
        qv = vector(q)
        docs = [tokens(c["title"] + " " + c["text"]) for c, _ in self.rows]
        avg = sum(map(len, docs)) / max(1, len(docs))
        scored = []
        for (c, v), words in zip(self.rows, docs):
            counts = Counter(words)
            sparse = 0
            for term in set(q):
                df = sum(term in d for d in docs)
                idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
                tf = counts[term]
                sparse += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(words) / avg))
            dense = sum(a * b for a, b in zip(qv, v))
            # Require a lexical anchor even for vector matches; collisions aren't evidence.
            overlap = len(set(q) & set(words))
            score = sparse if mode == "bm25" else dense if mode == "vector" else sparse + max(0, dense)
            if overlap and score > 0:
                scored.append(dict(c, score=score, overlap=overlap))
        scored.sort(key=lambda x: (-x["score"], x["id"]))
        return scored[:top_k]
