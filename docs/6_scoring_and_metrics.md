# Step 6 — Scoring, metrics, and what the model is trained on

## 6.1 Metrics

* **Structure:** share of the true categories / series / cells that appear in the answer (e.g. 4 / 4 countries).
* **Within 5 %:** share of the true values that the model reads with an error of at most 5 % of the true value
  (relaxed accuracy, as used in chart question-answering benchmarks). Example: truth 63.0 years → 59.9 to 66.2 passes.
* **Within 2 %:** the same with 2 %, a stricter precision measure (63.0 → 61.8 to 64.3).
* **Mean error:** average of |model − truth| / truth over all values.
* **Failure flags:** `empty`, `constant` (one value everywhere), `repeated` (looping rows).

**Line chart:** answers are matched per country; each answered point is compared with the true curve at that year
(linear interpolation between true points, years within ±2.5 years of the range), so a model that writes other years
is still scored fairly (`score_line` in `finetune_video/vscore.py`, also used by `eval_video.py` when
`vlm_eval/score_tables.py` has no line scorer).

## 6.2 What the model learns from — and what it never sees

| Data | What it is | Used for |
|---|---|---|
| Synthetic charts | generated clips: made-up names, values and years, each with its exact table | **training only** |
| Banned names (`--strict`) | 23 real names from our charts (e.g. Japan, China, South Africa, India) | kept out of training (`excluded_names.json`) |
| Quest recordings | `line_clear.mp4` etc., 8 frames | **test only** |
| True tables (`ground_truth/`) | Kaggle / Gapminder data | **scoring only**, after the model has answered |
| Offset correction | the model's average bias | learnt on synthetic validation clips, never on the true table |

The training files prove this: `train.jsonl` lists only synthetic frames, `training_info.json` the number of synthetic
clips. Colab and Kaggle provide only the GPU; the model trains only on the files our scripts give it.

**Caveat:** the true tables come from public datasets, so the base model may have seen them in pre-training. The
untrained baseline (50 % within 5 %, values up to 22 % off) indicates it does not recall them; a control chart with
invented numbers is planned to confirm this.
