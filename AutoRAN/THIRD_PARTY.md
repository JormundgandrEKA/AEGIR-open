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
| RAN / `aegir_ran` (AEGIR-open) | Apache-2.0 (a separate repository; AutoRAN is meant to live beside it) |
| Python | PSF License |
| PyTorch (optional, GPU) | BSD-3-Clause style; its CUDA libraries (NVIDIA) come under NVIDIA's own licence terms |
| NumPy, pandas, SciPy | BSD-3-Clause |
| PyArrow | Apache-2.0 |
| Matplotlib | Matplotlib licence (PSF-based) |
| Plotly | MIT |
| pywebview (desktop window), pythonnet | BSD-3-Clause, MIT |
| Microsoft Edge WebView2 runtime | Microsoft's own licence terms; installed by Windows, not bundled |
| PyInstaller (builds the exe) | GPL-2.0 with a special exception that allows distributing built programs under any licence |

**Distributing an executable.** The 4+ GB Windows build contains PyTorch and NVIDIA CUDA libraries, so redistributing it means redistributing their licences too. This has not been reviewed, which is why the repository ships the build script and not the executable. If you publish a built executable later, check each licence above (and the files inside the build's `_internal/` folder), include the required notices, and consider a CPU-only build without the NVIDIA libraries.
