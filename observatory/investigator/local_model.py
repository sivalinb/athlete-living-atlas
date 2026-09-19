"""Load a trained, merged router from disk; no automatic downloads or remote code."""

from pathlib import Path
from training.prepare import prompt, LABELS


def classify(question, model_dir):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    path = Path(model_dir).resolve()
    if not (path / "config.json").is_file():
        raise ValueError("A trained merged model directory is required")
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, trust_remote_code=False)
    model.eval()
    inputs = tokenizer(prompt(question), return_tensors="pt")
    with torch.no_grad():
        output = model.generate(
            **inputs, max_new_tokens=16, do_sample=False, pad_token_id=tokenizer.eos_token_id
        )
    label = (
        tokenizer.decode(output[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        .strip()
        .splitlines()[0]
    )
    return label if label in LABELS else "review"
