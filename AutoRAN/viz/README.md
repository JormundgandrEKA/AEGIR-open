# Visualising AutoRAN results

`autoran frame` writes one Parquet file with a row per trial: label, categories, input state, split and every scorer's score
(`score_<name>` columns). Parquet reads in Python and R, so use whichever you prefer.

```
.venv\Scripts\python -m autoran frame            # data/derived/autoran/frame_<stamp>.parquet
.venv\Scripts\python viz\plots.py                # four starter plots into data/derived/autoran/plots/
```

## Python

```python
import pandas as pd
df = pd.read_parquet("data/derived/autoran/frame_<stamp>.parquet")
task = df[df["class"].isin(["positive_recruitment", "negative_completed"])]
task.groupby("sponsor_class")["class"].apply(lambda c: (c == "positive_recruitment").mean())
```

Plotly gives interactive charts: `import plotly.express as px; px.histogram(task, x="score_gpu_mlp", color="class", log_y=True)`.

## R

```r
library(arrow); library(dplyr); library(ggplot2)
df <- read_parquet("data/derived/autoran/frame_<stamp>.parquet")
task <- df |> filter(class %in% c("positive_recruitment", "negative_completed")) |> mutate(fail = class == "positive_recruitment")
task |> group_by(area) |> summarise(rate = mean(fail), n = n()) |> filter(n > 500) |>
  ggplot(aes(reorder(area, rate), rate)) + geom_col() + coord_flip() + labs(x = NULL, y = "share that failed to recruit")
```

The metrics file (`metrics_<stamp>.json`) holds the intervals, curves and calibration tables; `jsonlite::read_json` or `json.load` reads it.

## Notes
- `score_*` columns exist only for trials in the binary task (completed or failed to recruit); others are empty.
- Test the "clean" subset with `input_state in ("first_version", "never_updated", "current_unchanged")`, and remember it is a different kind of trial, not just a cleaner copy.
