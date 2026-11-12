# Control test: does the line-chart model work on any line chart with any values?

The professor's question after the 5 Nov meeting: does the fine-tuned model reach the same accuracy on **any** line chart
with **any** values, not only the Gapminder chart? This test answers it with new charts whose values are random
numbers that exist nowhere else: not online, not in Gapminder, not in training.

## The six control charts (`ground_truth/control/`)

| Recording name | Axes | Design | Values |
|---|---|---|---|
| `line_control_A` | Year × life expectancy | same layout as Gapminder: Brazil, Kenya, Norway, Peru, 1952–2007 every 5 years | 48 |
| `line_control_B` | Year × life expectancy | Egypt, Canada, Vietnam, 1960–2010 every 10 years, sharp rise and fall | 18 |
| `line_control_C` | Year × life expectancy | harder: 6 lines, 1950–2010 every 5 years | 78 |
| `linexy_control_D` | **Month × Sales (thousand units)** | Product A, B, C, months 1–12 | 36 |
| `linexy_control_E` | **Hour × Energy use (kWh)** | Station A–D, hours 0–22 every 2 | 48 |
| `linexy_control_F` | **Day × Price ($)** | Coffee, Bread, Milk, days 1–12, two decimals | 36 |

`line_*` charts use the life-expectancy prompt; `linexy_*` charts use a general prompt (header `Series,X,Y`: legend
name, x value, y value). For the DxR build, `dxr/<name>.csv` has readable column names (e.g. `product,month,sales`);
set the axis titles to the `x_axis` / `y_axis` in `MANIFEST.json` and the legend title to `legend_title`.

These charts are **test data only**: with `--strict`, their series names are also excluded from all synthetic
training data. Values come from a seeded random generator (`make_control_charts.py`, seed 20261120). `MANIFEST.json` stores the
sha256 of every truth table; it is committed to GitHub **before recording**, so the commit time proves the truth
tables were fixed before the model saw any video. `preview_*.png` shows how each chart should look.

## Steps

1. **Commit the truth tables first** (`git add control_test ground_truth/control && git commit -m "Control test: pre-registered random line charts" && git push`).
2. **Add the charts to the DxR app** with `make_dxr_specs.py`: it copies your working line-chart spec and swaps in the
   new data file, field names, axis titles and legend title, and adds the charts to `charts.json`
   (`python3 control_test/make_dxr_specs.py --package <Unity project>/Packages/com.vlm.dxrcharts`). Then in Unity:
   **DxR Charts → Copy charts to StreamingAssets** and **DxR Charts → 4. Build and Run on Quest**. Compare each chart
   in the headset with `preview_<name>.png`.
3. **Record on the Quest 2**, one video per chart, the same way as `line_clear`: slow, steady walk-around, about
   20 seconds, chart filling 60–80 % of the view, start facing it, do not go behind it. Name the files
   `line_control_A.mp4` … `line_control_C.mp4` and `linexy_control_D.mp4` … `linexy_control_F.mp4` (the name links the video to its truth table).
   Keep the original files: they are the raw proof.
4. **Run `notebooks/Control_any_line_test.ipynb`** in Colab: it tests the run-4 model and the untrained model on every
   recording and makes, per recording, a proof video (title card with the truth hash → the raw recording → the 8
   frames the model saw → the result) and a slide image. If the other-axes charts (D–F) need it, cells 9–10 train and
   test **run 5**, one model for any line chart (synthetic only: 50 % any-axes charts, 50 % life-expectancy charts).

## Scripts

| File | What it does |
|---|---|
| `make_control_charts.py` | generates the random truth tables, DxR data files, previews and `MANIFEST.json` |
| `make_dxr_specs.py` | adds the control charts to the DxR app (data files, specs, `charts.json`) |
| `make_proof_video.py` | builds the downloadable proof video and slide image for one recording |

`finetune_video/eval_video.py` and `eval_median.py` automatically score a recording against
`ground_truth/control/<recording>.csv` when that file exists.
