#!/usr/bin/env python3
"""Run 3: LoRA fine-tuning of Qwen3.5-9B on synthetic walk-around VIDEOS (8 frames per example).

    python3 finetune_video/train_video_lora.py --data finetune_video/data --out lora_qwen35_video
    python3 finetune_video/train_video_lora.py --base unsloth/Qwen3.5-4B ...    # smaller model, e.g. on an L4
    python3 finetune_video/train_video_lora.py --load-4bit ...                  # less memory

Every example = all frames of one synthetic clip + the same prompt as the evaluation (vlm_eval/prompts.md, which
already says "These images are frames from a video") -> the clip's CSV. Only synthetic clips are used; the real
Quest videos and the ground_truth tables are never read here. Settings follow Unsloth's Qwen3.5 vision notebook
(16-bit LoRA, rank 16, vision + language layers). Batch 1 x 8 accumulation (video examples are large).
"""
import argparse
import importlib.util
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("run_local_vlm", os.path.join(ROOT, "vlm_eval", "run_local_vlm.py"))
vlm = importlib.util.module_from_spec(spec); spec.loader.exec_module(vlm)


def load(path, max_side):
    img = Image.open(path).convert("RGB")
    s = max_side / max(img.size)
    return img.resize((round(img.width * s), round(img.height * s))) if s < 1 else img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--base", default="unsloth/Qwen3.5-9B")
    ap.add_argument("--load-4bit", action="store_true")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--steps", type=int, help="optimizer steps (8 clips each); default from --epochs")
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--max-side", type=int, default=640, help="frame size in pixels (longest side)")
    ap.add_argument("--max-length", type=int, default=8192)
    ap.add_argument("--out", default=os.path.join(ROOT, "lora_qwen35_video"))
    a = ap.parse_args()

    from unsloth import FastVisionModel                      # import before transformers/trl
    from unsloth.trainer import UnslothVisionDataCollator
    from trl import SFTTrainer, SFTConfig

    prompts = {c: vlm.chart_prompt(c) for c in vlm.CHARTS}
    rows = [json.loads(l) for l in open(os.path.join(a.data, "train.jsonl"), encoding="utf-8")]
    data = [{"messages": [
        {"role": "user", "content": [{"type": "image", "image": load(os.path.join(a.data, f), a.max_side)} for f in r["frames"]]
                                    + [{"type": "text", "text": prompts[r["chart"]]}]},
        {"role": "assistant", "content": [{"type": "text", "text": r["answer"]}]}]} for r in rows]
    steps = a.steps or max(1, int(round(len(data) * a.epochs / 8)))
    print(f"{len(data)} training clips x {len(rows[0]['frames'])} frames, {steps} steps, base {a.base}")

    model, tokenizer = FastVisionModel.from_pretrained(a.base, load_in_4bit=a.load_4bit, use_gradient_checkpointing="unsloth", max_seq_length=a.max_length)
    model = FastVisionModel.get_peft_model(
        model, finetune_vision_layers=True, finetune_language_layers=True,
        finetune_attention_modules=True, finetune_mlp_modules=True,
        r=a.rank, lora_alpha=a.rank, lora_dropout=0, bias="none", random_state=3407)
    FastVisionModel.for_training(model)
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        data_collator=UnslothVisionDataCollator(model, tokenizer, resize="max", max_seq_length=a.max_length),
        train_dataset=data,
        args=SFTConfig(
            per_device_train_batch_size=1, gradient_accumulation_steps=8,
            warmup_steps=10, max_steps=steps, learning_rate=a.lr,
            logging_steps=5, optim="adamw_8bit", weight_decay=0.001, lr_scheduler_type="linear",
            seed=3407, output_dir=os.path.join(ROOT, "outputs_video"), report_to="none",
            remove_unused_columns=False, dataset_text_field="", dataset_kwargs={"skip_prepare_dataset": True},
            max_length=a.max_length))
    stats = trainer.train()
    model.save_pretrained(a.out)
    tokenizer.save_pretrained(a.out)
    json.dump({"base": a.base, "clips": len(data), "frames_per_clip": len(rows[0]["frames"]), "steps": steps, "rank": a.rank,
               "lr": a.lr, "max_side": a.max_side, "load_4bit": a.load_4bit,
               "train_runtime_s": stats.metrics.get("train_runtime"), "train_loss": stats.metrics.get("train_loss")},
              open(os.path.join(a.out, "training_info.json"), "w"), indent=2)
    print(f"Saved LoRA adapters to {a.out}  (loss {stats.metrics.get('train_loss')})")


if __name__ == "__main__":
    main()
