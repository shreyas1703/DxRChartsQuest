# VLM prompts for table extraction

Give the VLM one or more frames from the recording of **one** chart, plus the matching prompt below.
Ask for CSV only, with the exact header shown, so `score_tables.py` can score the answer directly.
Save the answer as e.g. `predictions/pie.csv`.

The prompts deliberately do **not** reveal the values, number of rows or category names. If your
study wants to test reading only (not discovering) the categories, add them to the prompt and note it.

---

## Pie chart (`pie`)

```
These images are frames from a video recorded in a VR headset. They show a 3D pie chart.
Recover the data table behind the chart.
Return ONLY CSV with this exact header and one row per slice, largest first:
Genre,Share_percent
Use the slice labels / legend for Genre. Estimate each slice's share of the whole pie in percent
(one decimal place). The shares must add up to 100.
```
Optional second question, if the chart title gives the unit and you want absolute values:
```
The chart title says the values are global sales in millions of units and the total is 8920.44.
Add a column Global_Sales_millions.
```

## Bar chart (`bar`) — one row of 3D bars

```
These images are frames from a video recorded in a VR headset. They show a 3D bar chart:
one bar per category along the horizontal axis, bar height on the vertical axis.
Recover the data table behind the chart.
Return ONLY CSV with this exact header, one row per bar, in the order shown left to right:
Clarity,Mean_price_usd
Use the axis labels under the bars for Clarity. Read each bar's height against the vertical axis
and give Mean_price_usd as a number (one decimal place, no $ sign).
```

## 3D scatter plot (`scatter`)

```
These images are frames from a video recorded in a VR headset. They show a 3D scatter plot.
Recover the data table behind the chart: one row per point.
Return ONLY CSV with this exact header:
Species,Bill_length_mm,Flipper_length_mm,Body_mass_g
Species is the point colour (see the legend). Read each coordinate from the axis with the same name.
```

## Line chart (`line`)

```
These images are frames from a video recorded in a VR headset. They show a line chart with one
coloured line per country and a marker at every data point.
Recover the data table behind the chart: one row per marker.
Return ONLY CSV with this exact header:
Country,Year,Life_expectancy
Country is the line colour (see the legend). Read Year from the horizontal axis (the markers sit on
exact years) and Life_expectancy from the vertical axis, one decimal place.
```

## Heatmap (`heatmap`)

```
These images are frames from a video recorded in a VR headset. They show a heatmap: one coloured
cell per year (columns) and month (rows); the colour bar on the right maps colour to a value.
Recover the data table behind the chart: one row per cell.
Return ONLY CSV with this exact header:
Year,Month,Passengers_thousands
Use the axis labels for Year and Month (three-letter month names). Estimate each cell's value by
matching its colour to the colour bar, as a whole number.
```
For a reading-only condition (no colour estimation), rebuild the charts with
`python3 data_prep/prepare_charts.py --labels values`: every cell (and every bar) then shows its number.

---

### Tips
* Use the same frames and prompts for every model you compare; record the model name, date and
  settings next to each prediction file.
* Try both a single frame and several frames (multi-image input) — 3D charts benefit from views at
  different angles (press **Y** on the left controller while recording for a slow turntable).
* Exploration questions (RQ2) can be answered from the recovered table, e.g. "Which clarity grade has the
  highest mean price?", "When did South Africa's life expectancy peak?", "Which month is busiest every year?"
* `ground_truth/manifest.json` documents how every true value was computed from the Kaggle data.
