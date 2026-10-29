"""Token-aware Python 2 -> Python 3 migration.

Python 2 code cannot be parsed by ``ast`` on Python 3, so rules run on the
``tokenize`` stream. That makes them syntax-aware: text inside strings and
comments is never touched. Anything ambiguous is reported, not rewritten.
"""
import ast
import io
import tokenize as tk

from .common import Finding, make_result

OPEN, CLOSE = ("(", "[", "{"), (")", "]", "}")
RENAMES = {"raw_input": "input", "xrange": "range"}
ATTR_RENAMES = {"iteritems": "items", "itervalues": "values", "iterkeys": "keys"}
FLAG_NAMES = {
    "unicode": "unicode() is gone in Python 3 (str); check text/bytes handling",
    "basestring": "basestring is gone in Python 3; use str (or (str, bytes))",
    "long": "long is gone in Python 3; int is unbounded",
    "unichr": "unichr() is gone in Python 3; use chr()",
    "reduce": "reduce() moved to functools",
    "execfile": "execfile() is gone in Python 3",
    "cmp": "cmp() is gone in Python 3",
}
LEGACY_MODULES = {
    "urllib2": "urllib.request / urllib.error", "ConfigParser": "configparser",
    "Queue": "queue", "cPickle": "pickle", "StringIO": "io.StringIO / io.BytesIO",
    "urlparse": "urllib.parse", "Tkinter": "tkinter",
}


def migrate(source: str) -> dict:
    findings, edits, seen = [], [], set()

    def add(rule, sev, line, msg, fixed=False, review=False):
        if (rule, line) not in seen:
            seen.add((rule, line))
            findings.append(Finding(rule, sev, line, msg, fixed, review))

    lines = io.StringIO(source).readlines()
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))
    off = lambda pos: starts[pos[0] - 1] + pos[1]

    try:
        toks = list(tk.generate_tokens(io.StringIO(source).readline))
    except (tk.TokenError, SyntaxError) as exc:
        add("PY_TOKENIZE_ERROR", "high", 1, f"Source could not be tokenized: {exc}", review=True)
        return make_result(source, None, findings)

    sig = [t for t in toks if t.type not in (tk.COMMENT, tk.NL)]
    depth, start = 0, True
    for i, t in enumerate(sig):
        s, prev = t.string, (sig[i - 1] if i else None)
        nxt = sig[i + 1] if i + 1 < len(sig) else None
        if t.type in (tk.NEWLINE, tk.INDENT, tk.DEDENT):
            start, depth = True, 0
            continue
        was_start, start = start, False
        if t.type == tk.OP:
            if s in OPEN:
                depth += 1
            elif s in CLOSE:
                depth = max(0, depth - 1)
            elif s == ";" and depth == 0:
                start = True
            elif s == ":" and depth == 0:
                start = True
            elif s == "<>":
                edits.append((off(t.start), off(t.end), "!="))
                add("PY_NOT_EQUAL", "low", t.start[0], "'<>' replaced by '!='", True)
            elif s == "/":
                add("PY_DIVISION", "medium", t.start[0],
                    "'/' on integers floors in Python 2 but is true division in Python 3; verify intent",
                    review=True)
            continue
        if t.type == tk.ERRORTOKEN and s == "`":
            add("PY_BACKTICK", "high", t.start[0], "Backtick repr was removed; use repr()", review=True)
            continue
        if t.type != tk.NAME:
            continue
        after_dot = prev is not None and prev.type == tk.OP and prev.string == "."
        if after_dot:
            if s in ATTR_RENAMES:
                edits.append((off(t.start), off(t.end), ATTR_RENAMES[s]))
                add("PY_DICT_ITER", "low", t.start[0],
                    f".{s}() -> .{ATTR_RENAMES[s]}() (views instead of lists/iterators)", True)
            elif s == "has_key":
                add("PY_HAS_KEY", "medium", t.start[0], "dict.has_key() removed; use 'key in d'", review=True)
            continue
        if s in RENAMES:
            edits.append((off(t.start), off(t.end), RENAMES[s]))
            add("PY_RENAME_" + s.upper(), "low", t.start[0], f"{s}() -> {RENAMES[s]}()", True)
        elif s in FLAG_NAMES:
            add("PY_REMOVED_" + s.upper(), "medium", t.start[0], FLAG_NAMES[s], review=True)
        elif was_start and s in ("import", "from") and nxt is not None and nxt.string in LEGACY_MODULES:
            add("PY_LEGACY_IMPORT", "medium", t.start[0],
                f"Module '{nxt.string}' was renamed/moved: use {LEGACY_MODULES[nxt.string]}", review=True)
        elif was_start and s == "print":
            _print_stmt(sig, i, off, edits, add)
        elif was_start and s == "except":
            _except_clause(sig, i, off, edits, add)
        elif was_start and s == "raise":
            _raise_stmt(sig, i, add)
        elif was_start and s == "exec" and nxt is not None and nxt.string != "(":
            add("PY_EXEC", "high", t.start[0], "exec statement is a function in Python 3", review=True)

    migrated = source
    for a, b, text in sorted(set(edits), key=lambda e: (e[0], e[1]), reverse=True):
        migrated = migrated[:a] + text + migrated[b:]
    findings.sort(key=lambda f: f.line)
    return make_result(source, migrated, findings)


def _print_stmt(sig, i, off, edits, add):
    t, nxt = sig[i], sig[i + 1]
    line = t.start[0]
    if nxt.type in (tk.NEWLINE, tk.ENDMARKER) or (nxt.type == tk.OP and nxt.string == ";"):
        edits.append((off(t.end), off(t.end), "()"))
        add("PY_PRINT_STATEMENT", "medium", line, "print statement -> print() call", True)
        return
    if nxt.type == tk.OP and nxt.string == ">>":
        add("PY_PRINT_CHEVRON", "high", line, "'print >>stream' needs manual conversion to print(..., file=stream)", review=True)
        return
    is_stmt = nxt.type in (tk.NAME, tk.STRING, tk.NUMBER) or (
        nxt.type == tk.OP and nxt.string in ("-", "+", "~", "[", "{"))
    if not is_stmt:
        return
    j, d = i + 1, 0
    while j < len(sig):
        u = sig[j]
        if u.type == tk.OP and u.string in OPEN:
            d += 1
        elif u.type == tk.OP and u.string in CLOSE:
            d -= 1
        if u.type in (tk.NEWLINE, tk.ENDMARKER) or (u.type == tk.OP and u.string == ";" and d == 0):
            break
        j += 1
    last = sig[j - 1]
    if last.type == tk.OP and last.string == ",":
        add("PY_PRINT_TRAILING_COMMA", "high", line,
            "print with trailing comma suppressed the newline; use print(..., end=' ')", review=True)
        return
    edits.append((off(t.end), off(nxt.start), "("))
    edits.append((off(last.end), off(last.end), ")"))
    add("PY_PRINT_STATEMENT", "medium", line, "print statement -> print() call", True)


def _except_clause(sig, i, off, edits, add):
    d = 0
    for k in range(i + 1, len(sig)):
        u = sig[k]
        if u.type == tk.OP and u.string in OPEN:
            d += 1
        elif u.type == tk.OP and u.string in CLOSE:
            d -= 1
        elif u.type == tk.OP and u.string == ":" and d == 0:
            return
        elif u.type == tk.OP and u.string == "," and d == 0:
            edits.append((off(sig[k - 1].end), off(sig[k + 1].start), " as "))
            add("PY_EXCEPT_COMMA", "medium", sig[i].start[0], "'except X, e' -> 'except X as e'", True)
            return
        elif u.type == tk.NEWLINE:
            return


def _raise_stmt(sig, i, add):
    d = 0
    for k in range(i + 1, len(sig)):
        u = sig[k]
        if u.type == tk.NEWLINE:
            return
        if u.type == tk.OP and u.string in OPEN:
            d += 1
        elif u.type == tk.OP and u.string in CLOSE:
            d -= 1
        elif u.type == tk.OP and u.string == "," and d == 0:
            add("PY_RAISE_COMMA", "high", sig[i].start[0],
                "'raise E, msg' is invalid in Python 3; use raise E(msg)", review=True)
            return


def validate(source: str):
    """Syntax validation of Python 3 output (never executes the code)."""
    try:
        ast.parse(source)
        compile(source, "<migrated>", "exec")
        return [{"check": "python3_syntax", "status": "passed", "detail": "ast.parse + compile succeeded"}]
    except SyntaxError as exc:
        return [{"check": "python3_syntax", "status": "failed", "detail": f"line {exc.lineno}: {exc.msg}"}]
