# Security notes
- Single-file uploads; filenames containing `/`, `\`, `..`, NUL or leading `.` are rejected; extension allow-list per migration; 200 KB cap.
- Uploaded code is **never executed**. Validation = `ast.parse`/`compile` for Python and `@babel/parser` (parse only) for JSX.
- Secret patterns (AWS keys, private key blocks, hard-coded credentials) are flagged by line; values are withheld from findings and reports.
- UI renders all content with `textContent` (no HTML injection).
- No external AI or network calls are made by the application.
- Docker compose runs read-only, with all capabilities dropped. If you later add execution of uploaded tests, use dedicated sandbox workers: a container alone is not a hard boundary.
- Not implemented: authentication/authorization. Do not expose this service to untrusted users as-is.
