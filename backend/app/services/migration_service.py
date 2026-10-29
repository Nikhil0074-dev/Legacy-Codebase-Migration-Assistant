"""Orchestrates detect -> analyze -> transform -> validate -> record."""
import hashlib
import uuid
from datetime import datetime, timezone

from ..migration import python2to3, react_class
from ..security import scan_secrets

REGISTRY = {
    "python2-to-python3": {
        "label": "Python 2 -> Python 3", "extensions": [".py"],
        "migrate": python2to3.migrate, "validate": python2to3.validate, "language": "python",
    },
    "react-class-to-function": {
        "label": "React class component -> function component (Hooks)", "extensions": [".jsx", ".js", ".tsx"],
        "migrate": react_class.migrate, "validate": react_class.validate, "language": "javascript",
    },
}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_language(filename: str, content: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".py":
        return "python"
    if ext in (".js", ".jsx"):
        return "javascript"
    if ext in (".ts", ".tsx"):
        return "typescript"
    return "unknown"


def run_migration(filename: str, content: str, mtype: str) -> dict:
    spec = REGISTRY[mtype]
    result = spec["migrate"](content)
    findings = list(result["findings"])
    for label, line in scan_secrets(content):
        findings.append({"rule_id": "SECRET_DETECTED", "severity": "high", "line": line,
                         "message": f"Possible secret ({label}); value withheld. Do not send this file to external services.",
                         "auto_fixed": False, "review_required": True})
    validation = []
    if result["migrated"] is not None:
        validation = spec["validate"](result["migrated"])
    status = result["status"]
    if any(v["status"] == "failed" for v in validation):
        status = "failed"
    return {
        "id": uuid.uuid4().hex[:12], "filename": filename, "migration_type": mtype,
        "language": detect_language(filename, content),
        "original": content, "migrated": result["migrated"],
        "original_sha256": sha(content),
        "migrated_sha256": sha(result["migrated"]) if result["migrated"] is not None else None,
        "migration_status": status, "review": "pending",
        "findings": findings, "validation": validation,
        "created_at": now(), "history": [{"ts": now(), "event": "analyzed and transformed"}],
    }


def report_markdown(job: dict) -> str:
    f = job["findings"]
    out = [f"# Migration report: {job['filename']}", "",
           f"- Migration: {REGISTRY[job['migration_type']]['label']}",
           f"- Job id: `{job['id']}`", f"- Transformation status: **{job['migration_status']}**",
           f"- Review decision: **{job['review']}**",
           f"- Original SHA-256: `{job['original_sha256']}`",
           f"- Migrated SHA-256: `{job['migrated_sha256']}`", "", "## Validation"]
    out += [f"- {v['check']}: **{v['status']}** — {v['detail']}" for v in job["validation"]] or ["- No validation ran (no migrated output)."]
    out += ["", "## Findings", "", "| Rule | Severity | Line | Auto-fixed | Needs review | Message |", "|---|---|---|---|---|---|"]
    out += [f"| {x['rule_id']} | {x['severity']} | {x['line']} | {'yes' if x['auto_fixed'] else 'no'} | "
            f"{'yes' if x['review_required'] else 'no'} | {x['message']} |" for x in f] or ["| – | – | – | – | – | none |"]
    manual = [x for x in f if x["review_required"]]
    out += ["", "## Manual actions required", ""] + ([f"- Line {x['line']}: {x['message']}" for x in manual] or ["- None identified by the rules."])
    out += ["", "## Limitations", "",
            "Validation here checks syntax only; uploaded code is never executed. Passing checks do not prove behavioural equivalence — run your own test suite before merging."]
    return "\n".join(out) + "\n"
