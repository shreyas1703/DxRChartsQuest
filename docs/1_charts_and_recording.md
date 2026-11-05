# Step 1 — Charts, recordings and frames

## 1.1 Charts built with DxR

Five chart types were built with the DxR toolkit (Unity) from public Kaggle datasets, so the true table behind each
chart is known exactly. The true tables are in `ground_truth/`.

| Chart | Data (true table) | What the VLM must read | True values |
|---|---|---|---|
| Pie | video game sales share by genre | 8 genres, share in % | 8 |
| Bar (one row of 3D bars) | Diamonds data by clarity grade | 8 grades, bar height (mean price) and bar depth (count) | 16 |
| Line | Gapminder life expectancy, 4 countries | Japan, China, South Africa, India × 12 years (1952–2007) | 48 |
| Heatmap | airline passengers by year and month | 72 cells (colour) | 72 |
| 3D scatter | penguins (bill length, flipper length, body mass) | points by species | many points |

## 1.2 Recording on the Meta Quest 2

Each chart was run on the Quest 2 and recorded while walking around it (front, angled and steep views). For the
fine-tuning runs 3–4 we recorded new **clear** videos (`line_clear.mp4`, `pie_clear.mp4`): slow, steady walk-around,
chart filling about 60–80 % of the view, starting from the front and not going behind the chart.

## 1.3 Frames

* **Baseline study and runs 1–2 (single images):** one frame per second, 73 frames; 35 frames were tagged as
  `best`, `front`, `angled` or `steep` in `frames.csv`.
* **Runs 3–4 (video):** `finetune_video/sample_real_videos.py` takes 8 frames spread evenly over the whole recording
  (first and last second dropped) and writes `real_clips/<video>/f0.jpg … f7.jpg` and `real_clips/real.jsonl`.
  The chart is detected from the file name (`line_clear.mp4` → `line`).

```bash
python3 finetune_video/sample_real_videos.py ~/Desktop/quest_videos --charts line pie      # 640 px wide
python3 finetune_video/sample_real_videos.py /content/videos --charts line --width 800      # sharper, for run 4
```

The recordings and frames are **test data only**; they are never used for training.
