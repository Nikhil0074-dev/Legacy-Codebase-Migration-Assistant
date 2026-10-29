"""Input validation and secret detection."""
import re

MAX_BYTES = 200_000
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Hard-coded credential", re.compile(r"(?i)(api[_-]?key|secret|passwd|password|token)\s*[=:]\s*['\"][^'\"\s]{8,}['\"]")),
]


def safe_filename(name: str) -> str:
    """Single-file uploads only: reject anything resembling a path."""
    if not isinstance(name, str) or not name.strip() or len(name) > 255:
        raise ValueError("Invalid filename")
    if "\x00" in name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise ValueError("Filename must not contain path components")
    if not re.fullmatch(r"[\w\-. ]+", name):
        raise ValueError("Filename contains unsupported characters")
    return name


def scan_secrets(content: str):
    """Return [(label, line)] — never the secret value itself."""
    hits = []
    for no, line in enumerate(content.splitlines(), 1):
        for label, pat in SECRET_PATTERNS:
            if pat.search(line):
                hits.append((label, no))
    return hits
