# Step 3 — Runs 1 and 2: LoRA fine-tuning of Qwen3-VL-8B on synthetic images

Code: `finetune/` (`make_dataset.py`, `train_lora.py`, `eval_vlm.py`) · Colab A100 · Unsloth + TRL `SFTTrainer`.

## Approach

1. **Generate** thousands of DxR-style charts with random data and random viewing angles, each saved with its exact
   CSV answer. With `--strict`, the real names and values of our charts never appear in training.
2. **Fine-tune** LoRA adapters on Qwen3-VL-8B with the same prompt and CSV format as the evaluation.
3. **Test** base vs fine-tuned on the 35 tagged Quest frames (never used for training) plus 20 unseen generated charts.

Why generated data: we only have 5 real charts; generated charts give unlimited labelled examples, and the real
tables never appear in training, so the test is fair.

## Run 1

* 1,200 generated charts, images resized to 512 px, 150 steps; loss 1.84 → 0.33.

| Within 5 % | Best frame: base → LoRA | Front frames: base → LoRA | Generated charts: base → LoRA |
|---|---|---|---|
| Pie | 13 → 38 % | 13 → 31 % | 10 → 30 % |
| Line | 67 → 88 % | 27 → 48 % | 72 → 73 % |
| Bar height | 13 → 13 % | 13 → 6 % | 6 → 6 % |
| Bar depth | 0 → 0 % | 0 → 0 % | 13 → 6 % |
| Heatmap | 13 → 8 % | 6 → 6 % | 9 → 35 % |
| Scatter points | 2 → 0 % | 1 → 3 % | – |

* Pie about 3× better, line +21 points. Scatter no longer loops (0 of 7 answers, base 7 of 7) but lists fewer points.
* **Domain gap:** the model learned to read colours on flat generated heatmaps, but the DxR heatmap is a 3D panel.
* **Bars not learned**, even on generated bars; likely cause: 512 px images blur bar tops and depth ticks.

## Run 2 — fixes for each run-1 weakness

| Run-1 weakness | Change in run 2 |
|---|---|
| Fine detail lost | train at 896 px, the same size as testing (was 512 px) |
| Bars not learned | 30 % bars (was 24 %), clustered heights, readable depth axis |
| Heatmap domain gap | half the heatmaps drawn as 3D panels like DxR; 28 % heatmaps |
| Colour read by shade only | colour and lighting shifts, so values must be read against the colour bar |
| Too little data | 3,000 training charts (was 1,200), stronger viewing angles |

Trained 29 Oct 2026: 375 steps, 29 min, loss 2.02 → 0.29 (adapters `dxr_lora/lora_qwen3vl_v2`, 196 MB, in Google
Drive). Its test on the Quest frames was not completed before we moved to video input (run 3).

## Lesson carried into run 3

Single frames lose information that a walk-around contains, and Qwen3.5 is a newer, stronger model; run 3 therefore
trains on whole videos (8 frames) instead of single images.
