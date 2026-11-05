# Step 4 — Run 3: Qwen3.5-9B + LoRA on synthetic 8-frame videos

Code: `finetune_video/` · notebook `finetune_video/Run3_one_chart.ipynb` · Colab A100 80 GB.

## 4.1 Synthetic video dataset — `make_video_dataset.py`

* Each example is a short **walk-around clip of 8 frames** (640 × 480) of one made-up chart: flat charts are seen
  with a sweeping yaw, 3D charts (bar, scatter, heatmap) with a moving camera; each clip keeps one "headset look"
  (background, lighting, jitter).
* Every clip is saved with its exact CSV answer: `clips/<split>_<chart>_<n>/f*.jpg` + `train.jsonl` / `val.jsonl`
  records `{"frames", "chart", "answer"}`.
* `--strict` excludes 23 real names (genres, clarity grades, countries, species from `ground_truth/*.csv` + a built-in
  list) and the heatmap years 1949–1960, written to `excluded_names.json`.
* `--charts line` builds one chart type at a time (the plan: line first, then pie, then the others).

```bash
python finetune_video/make_video_dataset.py --strict --charts line --train 1000 --val 30 --out finetune_video/data_line
```

## 4.2 LoRA training — `train_video_lora.py`

* Base `unsloth/Qwen3.5-9B` loaded with Unsloth `FastVisionModel` (16-bit on A100, `--load-4bit` on T4).
* LoRA rank 16, alpha 16, dropout 0, on **vision and language** layers (attention + MLP): 51 M of 9.46 B parameters.
* Each training example = the 8 frames as 8 images + the evaluation prompt (which says the images are frames from a
  video) → the clip's CSV.
* `UnslothVisionDataCollator(..., resize="max", max_seq_length=…)`, batch 1 × gradient accumulation 8, AdamW 8-bit,
  learning rate 2e-4, linear schedule, 10 warm-up steps.

```bash
python finetune_video/train_video_lora.py --base unsloth/Qwen3.5-9B --data finetune_video/data_line --steps 125 --max-length 8192 --out lora_qwen35_line
```

## 4.3 Evaluation — `eval_video.py`

* Loads base or base + adapter, asks once per clip with greedy decoding (thinking turned off), extracts the CSV and
  scores it. Real clips come from `real_clips/real.jsonl`; `--videos line_clear` selects one recording; `--val` adds
  synthetic validation clips with known answers.
* `--compare` builds a table of all models in `results_video.csv`.

## 4.4 Run 3 result (line chart)

1,000 clips × 8 frames, 640 px, 125 steps, 25 min on A100, final loss 0.187.

On the real recording `line_clear`: **47 of 48 values within 5 % (97.9 %)**, 35 within 2 %, mean error 1.68 %,
largest error 5.2 % (China 1952). On 10 unseen synthetic clips: 97 % within 5 %, mean error 0.64 %.
Raw answer and tables: `results/line_run3/`.
