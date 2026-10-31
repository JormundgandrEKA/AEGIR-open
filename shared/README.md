# shared

What RÁN and AutoRAN both use, so neither depends on the other.

- `aegir_core/`: `governor.py` (the request governor, below), `http.py` (client, request budget, retries, redaction), `core.py` (paths, append-only store, sidecars),
  `context.py` (run context), `textclean.py` (markup to plain text, eligibility splitting), `grades.py` (licence and source grades),
  `ctgov_common.py` (ClinicalTrials.gov helpers).
- `config/aegir.json` (per-host rate limits, back-off, budgets) and `config/grades.json` (grade scale). A program's own `config/` folder overrides these.

Both programs find this folder next to themselves, so use a full clone of the repository. Standard library only.

## The request governor (keeps us out of 429, 502 and 503 trouble)

Every request from either program goes through `governor.py`:

- **Margin.** A host's limit is in `config/aegir.json` under `governor.hosts`, and we use only `governor.margin` of it (default **0.5**, 50%), so two fetchers on one connection stay inside the real limit. Change the margin globally or per host in that file.
- **Rolling quota.** Requests per window are counted, saved to disk and shared by every process on this computer, in `%LOCALAPPDATA%\AEGIR\state\governor.json` (`~/.local/state/aegir` elsewhere; override with `AEGIR_STATE_DIR`).
- **Server signals.** `Retry-After` and `RateLimit` or `X-RateLimit` headers are honoured. If a server says its window is almost used (including by others on the same connection), we wait for the reset.
- **Errors.** Any 429, 502, 503 or lost connection is announced, slows that host to half speed and pauses it. Three errors in 10 minutes stop that host for 15 minutes (doubling each time, up to 2 hours). The stop is saved, so a restart doesn't hammer the host, and a fetch resumes where it stopped.
- **Notes.** Every event is appended to `events.jsonl` next to the state file. AutoRAN shows them in its Fetch panel.

Figures: Hugging Face (500 requests per 5 minutes anonymous, 1,000 with a token) and NCBI (3 a second, 10 with a key) come from their documentation. ClinicalTrials.gov publishes no limit; 50 a minute per address is the community figure and is marked "assumed". Europe PMC's 10 a second comes from forum answers.
