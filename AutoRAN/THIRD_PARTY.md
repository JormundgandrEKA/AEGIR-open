# Third-party software and data

AutoRAN's own code is Apache-2.0. The first release ships **source and a build script only**. No third-party libraries or data are bundled in the repository.

## Data (downloaded by the user, never shipped here)
| Source | Terms | Notes |
|---|---|---|
| ClinicalTrials.gov, U.S. National Library of Medicine | https://clinicaltrials.gov/about-site/terms-conditions | Attribute NLM; state the data date; do not imply NLM or NIH endorsement. Some record text may be third-party copyrighted. AutoRAN requests a limited field set and no contact fields. |
| Open Targets, `clinical_trial_reason_to_stop` | Apache License 2.0 | Curated stop-reason texts; used to build and test the labeller. |

## Software AutoRAN uses (installed by the user, or bundled only in an executable they build themselves)
| Package | Licence (as published by the project; verify before redistributing a build) |
|---|---|
| RAN / `aegir_ran` (AEGIR-open) | Apache-2.0 (the `tool/` folder of this same repository) |
| Python | PSF License |
| PyTorch (optional, GPU) | BSD-3-Clause style; its CUDA libraries (NVIDIA) come under NVIDIA's own licence terms |
| NumPy, pandas, SciPy | BSD-3-Clause |
| PyArrow | Apache-2.0 |
| Matplotlib | Matplotlib licence (PSF-based) |
| Plotly | MIT |
| pywebview (desktop window), pythonnet | BSD-3-Clause, MIT |
| Microsoft Edge WebView2 runtime | Microsoft's own licence terms; installed by Windows, not bundled |
| PyInstaller (builds the exe) | GPL-2.0 with a special exception that allows distributing built programs under any licence |

**Distributing an executable.** The default build (`build.ps1`, about 170 MB) bundles Python, NumPy, pandas, PyArrow, Matplotlib and pywebview with their dependencies, and **no PyTorch or NVIDIA CUDA**; the GPU is used through a PyTorch the user installs themselves. The `-Full` build bundles PyTorch and CUDA (about 4 GB) and therefore NVIDIA's licence terms as well, so it is not meant for release. The licences listed above have not yet been reviewed file by file; before publishing a release, check them (and the files inside the build's `_internal/` folder). The lite zip carries LICENSE, NOTICE, THIRD_PARTY.md and DISCLAIMERS.md.
