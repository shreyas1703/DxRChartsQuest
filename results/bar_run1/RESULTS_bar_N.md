## Bar run 1: tested bar chart N

| Test chart | Bars | Untrained within 5 % | Fine-tuned (main) within 5 % | Mean error |
|---|---|---|---|---|
| bar3d_control_N | 8 | 50.0 % | 75.0 % | 6.53 % |

### bar3d_control_N

| Model | Within 5 % | Within 2 % | Mean error (% of value) | Average miss (units) | Missing |
|---|---|---|---|---|---|
| Untrained Qwen3.5-9B | **50.0 %** (4/8) | 3/8 | 15.13 % | 0.45 | 0 |
| Fine-tuned, whole video | **75.0 %** (6/8) | 4/8 | 6.75 % | 0.19 | 0 |
| **Fine-tuned, median of 7-frame votes (main)** | **75.0 %** (6/8) | 4/8 | 6.53 % | 0.18 | 0 |

**Per bar (main):**

| Bar (category / series) | True | Model | Error | Miss |
|---|---|---|---|---|
| Class Red / Round 1 | 8.3 | 8.2 | -1.2 % | -0.1 |
| Class Red / Round 2 | 5.1 | 5.1 | +0.0 % | +0 |
| Class Red / Round 3 | 7 | 7 | +0.0 % | +0 |
| Class Red / Round 4 | 4.3 | 3.9 | -9.3 % | -0.4 |
| Class Blue / Round 1 | 9.4 | 9.4 | +0.0 % | +0 |
| Class Blue / Round 2 | 5.9 | 6.1 | +3.4 % | +0.2 |
| Class Blue / Round 3 | 3.3 | 3.4 | +3.0 % | +0.1 |
| Class Blue / Round 4 | 1.7 | 2.3 | +35.3 % | +0.6 |
