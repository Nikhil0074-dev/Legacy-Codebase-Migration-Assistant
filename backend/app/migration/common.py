"""Shared data structures for migration rules."""
from dataclasses import dataclass, asdict


class Unsupported(Exception):
    """Raised when a construct is outside the safely automatable subset."""


@dataclass
class Finding:
    rule_id: str
    severity: str          # info | low | medium | high
    line: int
    message: str
    auto_fixed: bool = False
    review_required: bool = False

    def to_dict(self):
        return asdict(self)


def make_result(source, migrated, findings, validation_fn=None):
    """Build the standard migration result dict."""
    if migrated is None:
        status = "manual_review_required"
    elif any(f.review_required for f in findings):
        status = "needs_review"      # takes priority: warnings must never be hidden
    elif migrated == source:
        status = "no_changes"
    else:
        status = "safe"
    return {"migrated": migrated, "findings": [f.to_dict() for f in findings], "status": status}
