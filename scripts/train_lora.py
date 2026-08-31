#!/usr/bin/env python
"""Ready-to-run LoRA fine-tune (L-04). Trains on Quill's exported data and
writes a GGUF the local runtime can load. NOT run automatically — the Persona
tab shows sample counts and says when there is enough to bother.

Usage:
  # 1) export training data from the running instance
  curl -s http://127.0.0.1:8000/api/learning/export/sft > sft.jsonl   # (auth'd)
  # 2) train (needs a GPU + unsloth or peft)
  python scripts/train_lora.py --data sft.jsonl --base <hf-model> --out ./quill-lora

This script prefers Unsloth (fast, low-VRAM) and falls back to peft+transformers.
On a Blackwell-class card a pass over a few hundred edits is a weekend job at most.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_sft(path: str) -> list[dict]:
    rows = []
    for line in Path(path).read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        prompt = obj.get("prompt", "")
        if isinstance(prompt, dict):
            prompt = json.dumps(prompt)
        rows.append({"prompt": prompt, "completion": obj.get("completion", "")})
    return rows


def format_example(r: dict) -> str:
    return (f"### Reply in the operator's voice.\n{r['prompt']}\n"
            f"### Response:\n{r['completion']}")


def train_unsloth(rows, base, out, epochs, max_seq):
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import Dataset

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base, max_seq_length=max_seq, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(
        model, r=16, lora_alpha=16, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"])
    ds = Dataset.from_list([{"text": format_example(r)} for r in rows])
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=ds,
        dataset_text_field="text", max_seq_length=max_seq,
        args=TrainingArguments(per_device_train_batch_size=2,
                               gradient_accumulation_steps=4,
                               num_train_epochs=epochs, learning_rate=2e-4,
                               fp16=False, bf16=True, logging_steps=5,
                               output_dir=out, optim="adamw_8bit"))
    trainer.train()
    # write a GGUF the local runtime (Ollama/llama.cpp) can load (L-04)
    model.save_pretrained_gguf(out, tokenizer, quantization_method="q4_k_m")
    print(f"[lora] wrote GGUF under {out}")


def train_peft(rows, base, out, epochs, max_seq):
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              DataCollatorForLanguageModeling, Trainer,
                              TrainingArguments)

    tok = AutoTokenizer.from_pretrained(base)
    tok.pad_token = tok.pad_token or tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.bfloat16)
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=16, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))

    def tokenize(batch):
        return tok(batch["text"], truncation=True, max_length=max_seq)

    ds = Dataset.from_list([{"text": format_example(r)} for r in rows]).map(tokenize)
    Trainer(model=model, train_dataset=ds,
            data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
            args=TrainingArguments(output_dir=out, num_train_epochs=epochs,
                                   per_device_train_batch_size=2,
                                   learning_rate=2e-4, bf16=True, logging_steps=5)).train()
    model.save_pretrained(out)
    print(f"[lora] wrote adapter under {out}. Convert to GGUF with "
          f"llama.cpp/convert_lora_to_gguf.py for the local runtime.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="SFT JSONL from /api/learning/export/sft")
    ap.add_argument("--base", required=True, help="base HF model id (matches your draft model)")
    ap.add_argument("--out", default="./quill-lora")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--max-seq", type=int, default=1024)
    args = ap.parse_args()

    rows = load_sft(args.data)
    if len(rows) < 30:
        print(f"[lora] only {len(rows)} examples — the Persona tab is right, "
              f"collect more edits before training.")
        return
    print(f"[lora] training on {len(rows)} examples from {args.data}")
    try:
        train_unsloth(rows, args.base, args.out, args.epochs, args.max_seq)
    except ImportError:
        print("[lora] unsloth not available; falling back to peft+transformers")
        train_peft(rows, args.base, args.out, args.epochs, args.max_seq)


if __name__ == "__main__":
    main()
