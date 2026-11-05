# Step 5 — Run 4: line chart to 100 % within 5 %

Code: `finetune_video/` + `eval_median.py` · notebooks `notebooks/Run4_line_colab.ipynb`, `Run4_line_kaggle.ipynb` ·
trained on Colab A100 80 GB. Results: `results/line_run4/`.

## 5.1 What changed from run 3

| Setting | Run 3 | Run 4 |
|---|---|---|
| Synthetic training clips × frames | 1,000 × 8 | **2,000 × 8** |
| Frame size | 640 × 480 | **800 × 600** (`--size 800x600`, `--max-side 800`) |
| Gridlines on synthetic charts | major lines only | **major every 5 or 10; half also minor every 1 or 2.5** |
| LoRA rank · learning rate · batch | 16 · 2e-4 · 1 × 8 | same |
| Steps · max sequence length | 125 · 8,192 | **250 · 12,288** |
| Training time · final loss | 25 min · 0.187 | 67 min · **0.120** |

## 5.2 Evaluation with median voting and offset correction — `eval_median.py`

For each clip the model answers **9 times**: once with all 8 frames and 8 times with one frame left out (7-frame
"votes"; single frames were tried first and were worse, because the model is trained on videos). For every country and
year the **median** of the 9 values is taken.

An **offset correction** is learnt as the median signed error on **synthetic validation clips only** and subtracted
from the real answers (`median_cal`, `video_cal` rows). The true table is never used for it.

```bash
python finetune_video/eval_median.py --model lora_qwen35_line_r4 --name qwen35_r4_line --charts line \
    --real real_clips/real.jsonl --videos line_clear --val finetune_video/data_line800/val.jsonl --val-n 10 --max-side 800
```

## 5.3 Results on the real recording `line_clear` (48 Gapminder values)

| Model | Within 5 % | Within 2 % | Mean error | Largest error |
|---|---|---|---|---|
| Qwen3.5-9B untrained (baseline) | 50 % (24/48) | 11/48 | 7.43 % | 21.8 % |
| Run 3 | 97.9 % (47/48) | 35/48 | 1.68 % | 5.2 % |
| **Run 4, whole video** | **100 % (48/48)** | 19/48 | 2.38 % | 4.4 % |
| Run 4, median of 9 votes | 100 % | 21/48 | 2.30 % | 4.4 % |
| Run 4, median + offset (offset learnt = 0.0) | 100 % | 21/48 | 2.30 % | 4.4 % |

Synthetic validation (10 unseen clips): baseline 84 % within 5 %, run 4 **100 %** (mean error 0.18 %).

**What the untrained model did:** it read the x-axis tick labels (1950, 1955 … 2010) instead of the data years,
wrote Japan as a straight line (64, 65 … 76) and was about 21 % too low for India after 1985.

## 5.4 Every value: run 3 vs run 4 (life expectancy in years; ✗ = outside 5 %)

| Country | Year | Truth | Run 3 | Run 3 error | Run 4 | Run 4 error |
|---|---|---|---|---|---|---|
| Japan | 1952 | 63.0 | 64.1 | +1.7 % | 64.0 | +1.5 % |
| Japan | 1957 | 65.5 | 66.6 | +1.7 % | 66.9 | +2.1 % |
| Japan | 1962 | 68.7 | 69.5 | +1.1 % | 70.1 | +2.0 % |
| Japan | 1967 | 71.4 | 72.3 | +1.2 % | 72.7 | +1.8 % |
| Japan | 1972 | 73.4 | 74.2 | +1.1 % | 74.8 | +1.9 % |
| Japan | 1977 | 75.4 | 76.3 | +1.2 % | 76.7 | +1.8 % |
| Japan | 1982 | 77.1 | 78.4 | +1.7 % | 78.7 | +2.1 % |
| Japan | 1987 | 78.7 | 80.0 | +1.7 % | 80.0 | +1.7 % |
| Japan | 1992 | 79.4 | 80.9 | +1.9 % | 80.8 | +1.8 % |
| Japan | 1997 | 80.7 | 82.3 | +2.0 % | 82.3 | +2.0 % |
| Japan | 2002 | 82.0 | 84.0 | +2.4 % | 83.8 | +2.2 % |
| Japan | 2007 | 82.6 | 85.0 | +2.9 % | 84.7 | +2.5 % |
| China | 1952 | 44.0 | 46.3 | +5.2 % ✗ | 45.4 | +3.2 % |
| China | 1957 | 50.5 | 52.1 | +3.1 % | 52.1 | +3.1 % |
| China | 1962 | 44.5 | 45.6 | +2.5 % | 46.3 | +4.0 % |
| China | 1967 | 58.4 | 60.3 | +3.3 % | 59.7 | +2.3 % |
| China | 1972 | 63.1 | 63.8 | +1.1 % | 63.8 | +1.1 % |
| China | 1977 | 64.0 | 64.6 | +1.0 % | 64.5 | +0.8 % |
| China | 1982 | 65.5 | 66.2 | +1.0 % | 66.0 | +0.7 % |
| China | 1987 | 67.3 | 67.8 | +0.8 % | 68.0 | +1.1 % |
| China | 1992 | 68.7 | 69.5 | +1.2 % | 69.7 | +1.5 % |
| China | 1997 | 70.4 | 71.3 | +1.2 % | 71.6 | +1.7 % |
| China | 2002 | 72.0 | 73.2 | +1.6 % | 73.3 | +1.8 % |
| China | 2007 | 73.0 | 74.5 | +2.1 % | 74.3 | +1.8 % |
| South Africa | 1952 | 45.0 | 45.8 | +1.8 % | 46.3 | +2.9 % |
| South Africa | 1957 | 48.0 | 48.5 | +1.1 % | 49.7 | +3.6 % |
| South Africa | 1962 | 50.0 | 50.2 | +0.5 % | 51.5 | +3.1 % |
| South Africa | 1967 | 51.9 | 52.3 | +0.7 % | 53.3 | +2.6 % |
| South Africa | 1972 | 53.7 | 54.1 | +0.8 % | 55.2 | +2.8 % |
| South Africa | 1977 | 55.5 | 56.2 | +1.2 % | 57.0 | +2.7 % |
| South Africa | 1982 | 58.2 | 58.5 | +0.6 % | 59.7 | +2.6 % |
| South Africa | 1987 | 60.8 | 61.8 | +1.6 % | 62.2 | +2.2 % |
| South Africa | 1992 | 61.9 | 63.5 | +2.6 % | 63.4 | +2.4 % |
| South Africa | 1997 | 60.2 | 61.2 | +1.6 % | 61.8 | +2.6 % |
| South Africa | 2002 | 53.4 | 54.8 | +2.7 % | 55.0 | +3.1 % |
| South Africa | 2007 | 49.3 | 51.5 | +4.4 % | 51.5 | +4.4 % |
| India | 1952 | 37.4 | 38.2 | +2.2 % | 39.0 | +4.4 % |
| India | 1957 | 40.2 | 40.5 | +0.6 % | 41.7 | +3.6 % |
| India | 1962 | 43.6 | 44.3 | +1.6 % | 44.8 | +2.7 % |
| India | 1967 | 47.2 | 47.6 | +0.9 % | 48.4 | +2.6 % |
| India | 1972 | 50.7 | 50.8 | +0.3 % | 51.8 | +2.3 % |
| India | 1977 | 54.2 | 54.2 | -0.0 % | 55.6 | +2.6 % |
| India | 1982 | 56.6 | 57.5 | +1.6 % | 58.8 | +3.9 % |
| India | 1987 | 58.6 | 60.1 | +2.6 % | 60.5 | +3.3 % |
| India | 1992 | 60.2 | 61.8 | +2.6 % | 61.8 | +2.6 % |
| India | 1997 | 61.8 | 62.5 | +1.2 % | 62.8 | +1.7 % |
| India | 2002 | 62.9 | 63.8 | +1.5 % | 64.0 | +1.8 % |
| India | 2007 | 64.7 | 65.5 | +1.2 % | 65.5 | +1.2 % |

## 5.5 Interpretation

* **Run 4 is our best model:** the only one with all 48 values within 5 %, no value worse than 4.4 %, 100 % on unseen
  synthetic charts with 0.18 % mean error, and the lowest training loss.
* **Run 3 is more precise on average** (35 vs 19 values within 2 %, 1.68 vs 2.38 % mean error).
* **Run 4's remaining error is a steady offset:** every value is read about **+1.4 years too high**, never too low.
  The offset learnt on synthetic clips is 0.0, so it comes from the gap between our synthetic charts and the real DxR
  chart (axis placement, line width, headset perspective), not from the model's reading ability.
* **Next:** run 5 with run 4's settings and synthetic charts drawn in the DxR style; a control chart with invented
  numbers recorded on the Quest (rules out memory of the public Gapminder data); 2–3 more clear recordings; then pie,
  bar, heatmap and scatter with the same pipeline.
