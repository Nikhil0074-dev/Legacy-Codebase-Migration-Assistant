# Architecture

```
Browser (frontend/index.html)  ──HTTP/JSON──▶  FastAPI (backend/app/main.py)
                                                  │
                          migration_service.run_migration()
                 ┌────────────────┬──────────────┴───────────┐
          migration/python2to3   migration/react_class   security.scan_secrets
          (tokenize-based)       (bracket/string-aware parser)
                 └──────── validate(): ast+compile / @babel/parser (node) ───────┐
                                                                                 ▼
                         diffing.py (side-by-side + unified)      store.py (SQLite JSON docs)
```

Pipeline per job: **detect → analyze → transform → validate → record → human review → export**.
The original text is stored untouched next to the proposal and its SHA-256, and every review action is appended to the job history.

## Design rules
1. Deterministic rules first. Anything ambiguous becomes a finding with `review_required`, not a guess.
2. A transformation that fails validation is marked `failed` and cannot be accepted.
3. Findings withhold secret values; reports never echo them.
4. Uploaded code is parsed, never executed.

## Honest deviations from the proposal
The proposal describes a larger system; this implementation deliberately delivers a working, tested core. See `supported-migrations.md` ("Not implemented").
