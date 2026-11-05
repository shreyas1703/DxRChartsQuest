# Runs 1–2: LoRA fine-tuning of Qwen3-VL-8B on synthetic single images

| File | What it does |
|---|---|
| `make_dataset.py` | generates DxR-style charts (pie, bar, line, heatmap, scatter) with random data and viewing angles, each with its exact CSV answer; `--strict` keeps the real names and values out |
| `train_lora.py` | LoRA fine-tuning of Qwen3-VL-8B with Unsloth (Colab A100) using the evaluation prompt and CSV format |
| `eval_vlm.py` | base vs fine-tuned on the 35 tagged Quest frames and unseen generated charts; writes `results_ft.csv` and `compare.md` |

Run 1: 1,200 charts, 512 px, 150 steps. Run 2: 3,000 charts, 896 px, 375 steps, more bars and 3D heatmaps.
Details and results: [../docs/3_run1_run2_qwen3vl_lora.md](../docs/3_run1_run2_qwen3vl_lora.md).
