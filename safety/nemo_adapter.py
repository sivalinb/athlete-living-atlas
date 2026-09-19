"""Optional NeMo rail experiment over public synthetic prompts and a loopback model."""

from pathlib import Path


def check(question):
    from nemoguardrails import RailsConfig, LLMRails
    from observatory.investigator.provider import public_question

    if not public_question(question):
        raise ValueError("Only published synthetic questions are accepted")
    config = RailsConfig.from_content(yaml_content=(Path(__file__).with_name("nemo-config.yaml")).read_text())
    return LLMRails(config).generate(messages=[{"role": "user", "content": question}])
