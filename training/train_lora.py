"""Real causal-LM LoRA training, held-out comparison, adapter merge and readback."""

import argparse
import json
from pathlib import Path
from .prepare import dataset, prompt
from .metrics import metrics


def main():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model

    p = argparse.ArgumentParser()
    p.add_argument("--model", default="Qwen/Qwen3-1.7B-Base")
    p.add_argument("--out", default=".local/qwen-router")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--rank", type=int, default=8)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--device", choices=["cpu", "cuda", "mps"], default="cuda")
    a = p.parse_args()
    if a.epochs < 1 or a.rank < 1:
        p.error("Positive epochs and rank required")
    if a.device == "cuda" and not torch.cuda.is_available():
        p.error("CUDA unavailable. Use a GPU runtime, or explicitly select --device cpu/mps.")
    torch.manual_seed(42)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(a.model, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        a.model, trust_remote_code=False, torch_dtype=torch.float32 if a.device == "cpu" else torch.float16
    ).to(a.device)
    rows = dataset()
    train = [r for r in rows if r["split"] == "train"]
    valid = [r for r in rows if r["split"] == "validation"]

    def classify(model, question):
        inputs = tokenizer(prompt(question), return_tensors="pt").to(a.device)
        with torch.no_grad():
            generated = model.generate(
                **inputs, max_new_tokens=16, do_sample=False, pad_token_id=tokenizer.eos_token_id
            )
        return (
            tokenizer.decode(generated[0, inputs["input_ids"].shape[1] :], skip_special_tokens=True)
            .strip()
            .splitlines()[0]
        )

    model.eval()
    baseline = [classify(model, r["question"]) for r in valid]
    model = get_peft_model(
        model,
        LoraConfig(
            task_type="CAUSAL_LM",
            r=a.rank,
            lora_alpha=2 * a.rank,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj"],
        ),
    )
    model.config.use_cache = False
    optimizer = torch.optim.AdamW([x for x in model.parameters() if x.requires_grad], lr=a.learning_rate)
    history = []
    for epoch in range(a.epochs):
        model.train()
        losses = []
        for row in train:
            prefix = tokenizer(prompt(row["question"]), add_special_tokens=False)["input_ids"]
            suffix = tokenizer(row["label"] + tokenizer.eos_token, add_special_tokens=False)["input_ids"]
            ids = torch.tensor([prefix + suffix], device=a.device)
            labels = torch.tensor([[-100] * len(prefix) + suffix], device=a.device)
            optimizer.zero_grad()
            loss = model(input_ids=ids, labels=labels).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        history.append({"epoch": epoch + 1, "mean_loss": sum(losses) / len(losses)})
        print(json.dumps(history[-1]), flush=True)
    model.eval()
    model.config.use_cache = True
    tuned = [classify(model, r["question"]) for r in valid]
    model.save_pretrained(out / "adapter")
    tokenizer.save_pretrained(out / "adapter")
    merged = model.merge_and_unload()
    merged.save_pretrained(out / "merged")
    tokenizer.save_pretrained(out / "merged")
    smoke = [classify(merged, r["question"]) for r in valid[:5]]
    if smoke != tuned[:5]:
        raise RuntimeError("Merged model predictions changed")
    report = {
        "model": a.model,
        "method": "LoRA causal LM, answer-only loss",
        "epochs": a.epochs,
        "rank": a.rank,
        "validation_count": len(valid),
        "baseline": metrics([r["label"] for r in valid], baseline),
        "fine_tuned": metrics([r["label"] for r in valid], tuned),
        "loss_history": history,
        "merge_smoke_passed": True,
        "predictions": [
            {"id": r["id"], "expected": r["label"], "baseline": b, "fine_tuned": t}
            for r, b, t in zip(valid, baseline, tuned)
        ],
    }
    report["accuracy_delta"] = report["fine_tuned"]["accuracy"] - report["baseline"]["accuracy"]
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Saved trained adapter, merged model, loss history and held-out comparison locally.")


if __name__ == "__main__":
    main()
