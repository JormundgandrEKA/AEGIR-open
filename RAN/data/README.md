# data/

Everything RÁN fetches, derives or records is written here. It is created by running the tool and ignored by git, except this file.

| Folder | Holds |
| --- | --- |
| `raw/` | files exactly as received, one dated file each, with a `.meta.json` sidecar (url, time, sha256, grade, how collected) |
| `catalogue/` | append-only JSON Lines indexes; the latest line per key wins |
| `derived/` | flags, diffs, tallies, batch audits (new dated files, never edited) |
| `labels/` | per labeller: `labels.jsonl`, `notepad.jsonl`, `drafts.jsonl`, `sessions/`; and `batches/` |
| `scratch/` | exploratory pulls; never eligible for a gold set |
| `demo/` | sessions on the bundled demo, kept apart from real labels so they never enter the tally (setting `demo_output_dir` in `../shared/config/aegir.json`) |

Nothing here is deleted or overwritten by the tool. The repository ships no fetched data.
