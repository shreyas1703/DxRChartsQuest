# 3D bar charts: tested bar chart N

**Goal:** read every bar of a 3D bar chart from a Meta Quest 2 recording: the category (front axis), the series
(depth axis and legend) and the value (bar height).

## Tested bar chart

`bar3d_control_N`, *Test score by class and round*: 2 classes × 4 rounds = 8 bars, decimal values (0–10), built in
DxR with **no numbers printed on the bars**, recorded as a slow walk-around on the Quest 2.

- Truth table: `ground_truth/control/bar3d_control_N.csv` (random values, seed 20261115, fixed before recording).
- The chart's names (Class Red, Class Blue, Round 1–4) are banned from training (`--strict`).
- Preview: `ground_truth/control/preview_bar3d_control_N.png`.

## Training

Qwen3.5-9B + LoRA (rank 16), trained **only on synthetic 3D grouped bar charts** made by
`finetune_video/make_video_dataset.py --charts bar3d`: 2–6 categories × 1–4 series, values from decimals to
100,000, many topics, colours, backgrounds, camera paths and legends. Answer format: `Category,Series,Value`.
Notebook: `notebooks/Bar3D_run1c.ipynb` (checkpoint to Drive every 15 steps). The result below is from bar run 1, in
which about 30 % of the synthetic training charts still showed values on the bars; run 1c (this notebook) shows none.

## Result (median of 7-frame votes)

| Model | Bars within 5 % | Within 2 % | Mean error (% of value) | Average miss (points) |
|---|---|---|---|---|
| Untrained Qwen3.5-9B | 4 / 8 (50 %) | 3 / 8 | 15.13 % | 0.45 |
| **Fine-tuned (bar run 1)** | **6 / 8 (75 %)** | 4 / 8 | **6.53 %** | **0.18** |

| Bar | True | Model |
|---|---|---|
| Class Red / Round 1 | 8.3 | 8.2 |
| Class Red / Round 2 | 5.1 | 5.1 |
| Class Red / Round 3 | 7.0 | 7.0 |
| Class Red / Round 4 | 4.3 | 3.9 |
| Class Blue / Round 1 | 9.4 | 9.4 |
| Class Blue / Round 2 | 5.9 | 6.1 |
| Class Blue / Round 3 | 3.3 | 3.4 |
| Class Blue / Round 4 | 1.7 | 2.3 |

Files: `RESULTS_bar_N.md`, `results_bar_N.csv`, `bar3d_control_N_proof_result.png`.

## Insights

1. **Depth is readable:** all 8 bars were found and matched to the right class and round, including the rounds
   going back in depth.
2. **Tall bars are read precisely:** 5.1, 7.0 and 9.4 exactly; every bar above 5 is within 4 %.
3. **Small bars are hardest:** both misses are in round 4; a 0.6-point miss on a bar of 1.7 is 35 %.

## Reproduce

1. Add the chart to the DxR app: `python3 control_test/make_dxr_bar_tests.py --package <.../com.vlm.dxrcharts>`, then in
   Unity *DxR Charts → Copy charts to StreamingAssets* and *4. Build and Run on Quest*; record `bar3d_control_N.mp4`.
2. Run `notebooks/Bar3D_run1c.ipynb` in Colab (L4 or A100), cells 1–10.
