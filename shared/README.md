# shared

What RÁN and AutoRAN both use, so neither depends on the other.

- `aegir_core/`: `http.py` (client with shared rate limits, request budget, retries, redaction), `core.py` (paths, append-only store, sidecars),
  `context.py` (run context), `textclean.py` (markup to plain text, eligibility splitting), `grades.py` (licence and source grades),
  `ctgov_common.py` (ClinicalTrials.gov helpers).
- `config/aegir.json` (per-host rate limits, back-off, budgets) and `config/grades.json` (grade scale). A program's own `config/` folder overrides these.

Both programs find this folder next to themselves, so use a full clone of the repository. Standard library only.
