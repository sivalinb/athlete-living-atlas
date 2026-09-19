"""Layered application boundaries; keyword checks are not a complete injection detector."""

import re
import unicodedata


def normalize(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError("Question must contain 1–2000 characters")
    text = unicodedata.normalize("NFKC", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf").strip()


def input_policy(question):
    q = normalize(question).lower()
    if re.search(r"ignore .*instruction|system prompt|jailbreak|developer message|override .*rule", q):
        return "instruction_override"
    if re.search(r"\b(delete|drop|update|insert|upload|email|publish|send|execute|shell)\b", q):
        return "write_or_export_request"
    if re.search(r"api.?key|password|secret|token\b|latitude|longitude|home address|coordinates", q):
        return "restricted_data"
    if re.search(
        r"diagnos|medicat|prescri|disease|heart attack|safe to race|fit to race|treatment|\bshould i\b", q
    ):
        return "medical_decision"
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d{3}-\d{2}-\d{4}\b", q):
        return "personal_identifier"
    return None


def verify_selection(selected, allowed):
    if not isinstance(selected, list) or not selected or len(selected) > 3:
        raise ValueError("Expected one to three evidence identifiers")
    if any(not isinstance(x, str) or x not in allowed for x in selected):
        raise ValueError("Unrecognized evidence citation")
    return list(dict.fromkeys(selected))
