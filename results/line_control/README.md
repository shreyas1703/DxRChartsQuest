# Line chart: any chart, any values (runs 4–6)

## Headline: test chart F (Day × Price, 3 lines × 12 days = 36 values)
| Model | Training charts (all synthetic) | Within 5 % |
|---|---|---|
| Run 4 | life-expectancy charts only | 80.6 % (29/36) |
| Run 5 | any axes, flat charts | 86.1 % (31/36) |
| **Run 6** | any axes, DxR-like 3D charts | **94.4 % (34/36)** |

Run 6: 18/36 within 2 %, mean error 2.00 %, 0 values missing. Same Quest recording and scoring for every model.

## Test design
- Truth tables generated with a seeded random generator; sha256 fingerprints committed before recording (see git history of `ground_truth/control/`).
- Test charts are never used in training; their line names are banned from synthetic data (`--strict`).
- The model gets 8 frames from one Quest 2 walk-around video and gives one answer.

## All pre-registered test charts, first recording (`results_recording1.csv`)
| Chart | Run 4 | Run 5 | Run 6 |
|---|---|---|---|
| D · Month × Sales (36) | 0 % | 52.8 % | 58.3 % |
| E · Hour × Energy (48) | 0 % | 62.5 % | 66.7 % |
| F · Day × Price (36) | 80.6 % | 86.1 % | 94.4 % |

D and E have coarser gridlines (5 % ≈ 1/7–1/8 of a grid step vs 1/4 on F) and show a systematic upward bias from the 3D depth of DxR lines.

## Second recording, run 6 (`results_recording2.csv`)
D 50.0 %, E 75.0 %, F 66.7 %. The E upload was damaged and re-uploaded; F's last frame was unreadable and the video was re-encoded. Recording quality is the main open variable; next step is a fixed recording protocol with 3 recordings per chart.
