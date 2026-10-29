# Testing
Run `scripts/run-tests.sh` (or `cd backend && python -m pytest -v`).

| File | Covers |
|---|---|
| `test_python2to3.py` | each rule, negative cases (strings/comments/attributes), idempotency, invalid input, validation |
| `test_react_class.py` | conversion output, imports, multi-key state, props, bail-out cases, bracket scanner, Babel validation |
| `test_support.py` | diff generation, filename safety, secret scan, SQLite store |
| `test_api.py` | full upload→migrate→diff→review→export→report workflow, 404/400/409/422 paths |
| `test_security.py` | traversal names, size limit, no code execution, injection-in-comments, secret redaction |

Babel-based tests are skipped (and the UI shows `could_not_run`) when `backend/tools/node_modules` is missing.
Passing tests demonstrate the rules on the covered cases only; they do not prove equivalence for arbitrary code.
