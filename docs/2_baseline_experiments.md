# Step 2 — Baseline study: untrained Qwen3-VL-8B (answering RQ1)

## Setup

* Model: **Qwen3-VL-8B**, open-weight, run locally in LM Studio (later on Colab), temperature 0.3, 2–3 runs per condition.
* Prompt: `vlm_eval/prompts.md` — one prompt per chart that asks for the table as CSV with a fixed header.
* Scripts: `prepare_charts.py` (charts), `extract_frames.py` (frames), `experiment.py` (runs the conditions),
  `score_tables.py` (scoring).

## Four conditions

| Condition | Input to the VLM | Question |
|---|---|---|
| A · Best frame | the single clearest front frame | best case |
| B · Viewpoint | front, angled and steep frames, one at a time | effect of the 3D viewing angle |
| C · Several frames | 6 frames in one request, or the median of the B answers | does video help? |
| D · Structured prompt | best frame + "read ticks and legend first" | does prompting help? |

## Results (share of true values within 5 %, mean of 2–3 runs)

| Chart · value | Structure | A best | B front | B angled | B steep | C multi | D prompt |
|---|---|---|---|---|---|---|---|
| Pie · slice share | 8/8 | 8 | 13 | 13 | 0 | 8 | 13 |
| Bar · height (price) | 8/8 | 13 | 19 | 13 | 50 | 25 | 17 |
| Bar · depth (count) | 8/8 | 0 | 0 | 0 | 0 | 0 | 0 |
| Line · life expectancy | 4/4 | 74 | 38 | 33 | 33 | 71 | 65 |
| Heatmap · passengers | 72/72 | 13 | 18 | 9 | 9 | 13 | 20 |
| Scatter · points | ~1/3 | 4 | – | – | – | – | – |

## Findings

1. **Structure is easy, values are hard:** labels, legends and categories are read almost perfectly.
2. **Errors are systematic:** repeated runs give nearly the same wrong values.
3. **Depth and colour fail:** one constant value for every bar depth; mostly one value for every heatmap cell.
4. **Clear scales help:** the line chart, with ticks to read against, is the only one above 70 %.
5. **Frame quality beats tricks:** several frames and prompting add at most about 12 points.

**Answer to RQ1:** a VLM reliably recovers a chart's structure but reads its values only approximately, and fails on
depth and colour. This motivated fine-tuning (RQ2), steps 3–5.
