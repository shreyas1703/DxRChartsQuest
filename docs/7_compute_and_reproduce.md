# Step 7 — Compute, notebooks and lessons learned

## Notebooks

| Notebook | Where | What it runs |
|---|---|---|
| `finetune_video/Run3_one_chart.ipynb` | Colab | run 3, one chart at a time (`CHART = "line"`, then `"pie"`) |
| `notebooks/Run4_line_colab.ipynb` | Colab A100 or free T4 | run 4: quick result with the run-3 adapter, baseline, training, median evaluation, results vs truth; saves everything to Google Drive (`MyDrive/dxr_run4`) and resumes after a disconnect |
| `notebooks/Run4_line_kaggle.ipynb` | Kaggle free T4 | the same, run in the background with *Save & Run All (Commit)* |

GPU settings are chosen automatically: A100/L4 → 16-bit, 800 px, 2,000 clips; T4 (16 GB) → 4-bit, 640 px, 1,500 clips.

## Problems we hit and their fixes

| Problem | Cause | Fix |
|---|---|---|
| `No such file or directory: /content/dxr` | Colab session reset, upload cell not run | every cell starts with `%cd /content/dxr`; Run 4 notebook keeps the zip in Drive |
| `vlm_eval/run_local_vlm.py` missing | helper not in the project folder | `vlm_eval/run_local_vlm.py` added (reads prompts from `prompts.md`) |
| `Mismatch in image token count … truncation` | Unsloth collator cut 8-frame examples at 2,048 tokens | `max_seq_length` passed to `from_pretrained` and `UnslothVisionDataCollator` (8,192 / 12,288) |
| `score_tables has no attribute score_line` | line scorer missing | `finetune_video/vscore.py` fills in missing scorers |
| median of single frames worse than the video | model trained on 8-frame videos | votes are 7-frame subsets instead |
| A100 greyed out in Colab | compute units used up | free T4 settings (4-bit, 640 px) or Kaggle |

## Reproduce run 4 (line chart)

1. Mac: `python3 finetune_video/sample_real_videos.py <videos folder> --charts line`, then zip the project
   (see the root README).
2. Colab: open `notebooks/Run4_line_colab.ipynb`, choose a GPU, run the cells in order (cell 10 shows the accuracy
   table and every value outside 5 %).
