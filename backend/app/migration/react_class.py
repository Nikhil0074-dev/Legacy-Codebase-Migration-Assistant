"""React class component -> function component (carefully bounded subset).

Supported: one class per file, state via constructor or class property,
arrow/regular methods, render(), this.props, this.setState({...}) with
object literals. Everything else (lifecycle, refs, PureComponent, updater
functions, static members...) is reported and left for a human.
"""
import json
import os
import re
import subprocess
import textwrap

from .common import Finding, Unsupported, make_result

CLASS_RE = re.compile(r"class\s+(\w+)\s+extends\s+(?:React\.)?(Pure)?Component\s*\{")
LIFECYCLE = {
    "componentDidMount", "componentDidUpdate", "componentWillUnmount", "shouldComponentUpdate",
    "getSnapshotBeforeUpdate", "componentDidCatch", "componentWillMount", "componentWillReceiveProps",
    "componentWillUpdate", "UNSAFE_componentWillMount", "UNSAFE_componentWillReceiveProps",
    "UNSAFE_componentWillUpdate", "getDerivedStateFromProps", "getDerivedStateFromError",
}
ARROW_RE = re.compile(r"\s*(async\s+)?(\([^)]*\)|\w+)\s*=>\s*\{")
IMPORT_RE = re.compile(
    r"import\s+(?:(?P<default>\w+)\s*,?\s*)?(?:\{(?P<named>[^}]*)\}\s*)?from\s*(?P<q>['\"])react(?P=q)\s*(?P<semi>;?)")
TOOLS = os.path.join(os.path.dirname(__file__), "..", "..", "tools")


def _skip_string(s, i):
    q, i = s[i], i + 1
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == q:
            return i + 1
        i += 1
    return i


def find_close(s, i):
    """Index of the bracket closing s[i]; aware of strings and comments."""
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack, j = [s[i]], i + 1
    while j < len(s):
        c = s[j]
        if s.startswith("//", j):
            k = s.find("\n", j)
            j = len(s) if k < 0 else k
            continue
        if s.startswith("/*", j):
            k = s.find("*/", j + 2)
            j = len(s) if k < 0 else k + 2
            continue
        if c == "`":
            j = _skip_string(s, j)
            continue
        if c in "'\"":
            before = s[:j].rstrip()
            # an apostrophe in JSX text ("Don't") is not a string start
            if not before or before[-1] in "(,=:[{?&|+!;" or before.endswith("return"):
                j = _skip_string(s, j)
                continue
        if c in pairs:
            stack.append(c)
        elif c in ")}]":
            if pairs[stack[-1]] != c:
                raise Unsupported("Unbalanced brackets; cannot parse class safely")
            stack.pop()
            if not stack:
                return j
        j += 1
    raise Unsupported("Unbalanced brackets; cannot parse class safely")


def split_top(text):
    parts, cur, i = [], 0, 0
    while i < len(text):
        c = text[i]
        if c in "({[":
            i = find_close(text, i) + 1
            continue
        if c in "'\"`":
            i = _skip_string(text, i)
            continue
        if c == ",":
            parts.append(text[cur:i])
            cur = i + 1
        i += 1
    parts.append(text[cur:])
    return [p.strip() for p in parts if p.strip()]


def parse_members(body, base):
    """Return [(kind, name, args, text, abs_offset)]."""
    members, i, n = [], 0, len(body)
    mem_re = re.compile(r"(static\s+|async\s+|get\s+|set\s+)?(\w+)\s*")
    while True:
        while i < n and (body[i].isspace() or body[i] == ";"):
            i += 1
        if body.startswith("//", i):
            k = body.find("\n", i)
            i = n if k < 0 else k
            continue
        if body.startswith("/*", i):
            k = body.find("*/", i + 2)
            i = n if k < 0 else k + 2
            continue
        if i >= n:
            return members
        m = mem_re.match(body, i)
        if not m:
            raise Unsupported(f"Unrecognised class member near: {body[i:i+30]!r}")
        if m.group(1):
            raise Unsupported(f"Member '{m.group(2)}' uses '{m.group(1).strip()}', which is not auto-convertible")
        name, j = m.group(2), m.end()
        pos = base + i
        if j < n and body[j] == "(":
            pe = find_close(body, j)
            k = pe + 1
            while k < n and body[k].isspace():
                k += 1
            if k >= n or body[k] != "{":
                raise Unsupported(f"Malformed method '{name}'")
            be = find_close(body, k)
            members.append(("method", name, body[j + 1:pe].strip(), body[k + 1:be], pos))
            i = be + 1
        elif j < n and body[j] == "=":
            am = ARROW_RE.match(body, j + 1)
            if am and not am.group(1):
                k = am.end() - 1
                be = find_close(body, k)
                members.append(("method", name, am.group(2).strip("() ").strip(), body[k + 1:be], pos))
                i = be + 1
            elif name == "state":
                k = j + 1
                while k < n and body[k].isspace():
                    k += 1
                if k >= n or body[k] != "{":
                    raise Unsupported("state initializer must be an object literal")
                be = find_close(body, k)
                members.append(("state", name, "", body[k:be + 1], pos))
                i = be + 1
            else:
                raise Unsupported(f"Class property '{name}' is not auto-convertible")
        else:
            raise Unsupported(f"Unrecognised class member '{name}'")


def _setter(k):
    return "set" + k[0].upper() + k[1:]


def _parse_state(obj_text):
    entries = {}
    for en in split_top(obj_text.strip()[1:-1]):
        mm = re.match(r"(\w+)\s*:\s*(.*)$", en, re.S)
        if not mm:
            raise Unsupported("State uses shorthand/spread/computed keys")
        entries[mm.group(1)] = mm.group(2).strip()
    return entries


def _ctor_state(body):
    body = re.sub(r"super\s*\([^)]*\)\s*;?", "", body)
    body = re.sub(r"this\.(\w+)\s*=\s*this\.\1\.bind\(this\)\s*;?", "", body)
    sm = re.search(r"this\.state\s*=\s*\{", body)
    if not sm:
        rest, obj = body, None
    else:
        e = find_close(body, sm.end() - 1)
        obj = body[sm.end() - 1:e + 1]
        rest = body[:sm.start()] + body[e + 1:]
    if re.sub(r"[;\s]|//[^\n]*", "", rest):
        raise Unsupported("Constructor contains logic beyond state initialisation")
    return obj


def _rewrite_setstate(text, keys, notes):
    out, i = [], 0
    while True:
        k = text.find("this.setState", i)
        if k < 0:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:k])
        p = k + len("this.setState")
        while p < len(text) and text[p].isspace():
            p += 1
        if p >= len(text) or text[p] != "(":
            raise Unsupported("Unusual setState usage")
        e = find_close(text, p)
        args = split_top(text[p + 1:e])
        if len(args) != 1 or not (args[0].startswith("{") and args[0].endswith("}")):
            raise Unsupported("setState with updater function or callback needs manual review")
        calls = []
        for en in split_top(args[0][1:-1]):
            mm = re.match(r"(\w+)\s*:\s*(.*)$", en, re.S)
            if not mm or mm.group(1) not in keys:
                raise Unsupported("setState touches unknown or computed state keys")
            key, val = mm.group(1), mm.group(2).strip()
            pat = r"this\.state\." + key + r"\b"
            if re.search(pat, val):
                prev = "prev" + key[0].upper() + key[1:]
                val = re.sub(pat, prev, val)
                body = f"({val})" if val.startswith("{") else val
                calls.append(f"{_setter(key)}(({prev}) => {body})")
                notes.append(f"setState of '{key}' depends on its previous value: functional update used")
            else:
                calls.append(f"{_setter(key)}({val})")
        cur = "".join(out)
        before = cur.rstrip()
        if len(calls) > 1 and before and before[-1] not in ";{}":
            raise Unsupported("Multi-key setState used inside an expression")
        indent = re.match(r"[ \t]*", cur[cur.rfind("\n") + 1:]).group()
        out.append((";\n" + indent).join(calls))
        i = e + 1


def _rewrite_this(text, keys, methods):
    def state_read(m):
        if m.group(1) not in keys:
            raise Unsupported(f"Read of unknown state key '{m.group(1)}'")
        return m.group(1)
    text = re.sub(r"this\.state\.(\w+)", state_read, text)
    text = re.sub(r"this\.props\b", "props", text)
    text = re.sub(r"this\.(\w+)", lambda m: m.group(1) if m.group(1) in methods else m.group(0), text)
    if re.search(r"\bthis\b", text):
        raise Unsupported("Remaining 'this' usage (destructuring, refs, instance fields) needs manual conversion")
    return text


def _reindent(body, spaces):
    text = textwrap.dedent(body.strip("\n")).strip("\n")
    pad = " " * spaces
    return "\n".join(pad + ln if ln.strip() else "" for ln in text.splitlines())


def _rewrite_import(src, hooks):
    m = IMPORT_RE.search(src)
    if not m:
        return src, False
    default = m.group("default")
    named = [n.strip() for n in (m.group("named") or "").split(",") if n.strip()]
    named = [n for n in named if n not in ("Component", "PureComponent")]
    if hooks and "useState" not in named:
        named.append("useState")
    q, semi = m.group("q"), m.group("semi")
    if not default and not named:
        return src[:m.start()] + src[m.end():].lstrip("\n"), True
    parts = ([default] if default else []) + ([("{ " + ", ".join(named) + " }")] if named else [])
    return src[:m.start()] + f"import {', '.join(parts)} from {q}react{q}{semi}" + src[m.end():], True


def migrate(source: str) -> dict:
    findings = []
    m = CLASS_RE.search(source)
    line_of = lambda pos: source.count("\n", 0, pos) + 1
    if not m:
        findings.append(Finding("REACT_NO_CLASS", "info", 1, "No eligible React class component found"))
        return make_result(source, source, findings)
    try:
        if CLASS_RE.search(source, m.end()):
            raise Unsupported("Multiple class components in one file; split the file first")
        if m.group(2):
            raise Unsupported("PureComponent: wrap the function in React.memo manually")
        cend = find_close(source, m.end() - 1)
        members = parse_members(source[m.end():cend], m.end())
        life = [mem for mem in members if mem[1] in LIFECYCLE]
        for mem in life:
            findings.append(Finding("REACT_LIFECYCLE", "high", line_of(mem[4]),
                f"Lifecycle method '{mem[1]}' does not map 1:1 to useEffect; convert manually", review_required=True))
        if life:
            raise Unsupported("Lifecycle methods present")
        name = m.group(1)
        state, ctor_seen = {}, False
        for kind, mname, args, text, pos in members:
            if kind == "state" or mname == "constructor":
                obj = text if kind == "state" else _ctor_state(text)
                if obj is not None:
                    if state:
                        raise Unsupported("State declared twice")
                    state = _parse_state(obj)
        methods = [mem for mem in members if mem[0] == "method" and mem[1] not in ("constructor", "render")]
        renders = [mem for mem in members if mem[1] == "render"]
        if len(renders) != 1:
            raise Unsupported("Component must have exactly one render() method")
        mnames = {mem[1] for mem in methods}
        if mnames & set(state) or mnames & {_setter(k) for k in state}:
            raise Unsupported("Method name collides with a state variable or setter")
        notes = []
        pieces = []
        for _k, mname, args, text, _pos in methods:
            t = _rewrite_this(_rewrite_setstate(text, state, notes), state, mnames)
            pieces.append(f"  function {mname}({args}) {{\n{_reindent(t, 4)}\n  }}")
        rtext = _rewrite_this(_rewrite_setstate(renders[0][3], state, notes), state, mnames)
        render_code = _reindent(rtext, 2)
        body_text = "\n".join(pieces) + render_code
        sig = "props" if re.search(r"\bprops\b", body_text) else ""
        hooks = "".join(f"  const [{k}, {_setter(k)}] = useState({v});\n" for k, v in state.items())
        func = f"function {name}({sig}) {{\n{hooks}"
        func += ("\n" if hooks and pieces else "") + "\n\n".join(pieces)
        func += ("\n\n" if pieces else ("\n" if hooks else "")) + render_code + "\n}"
        new_src = source[:m.start()] + func + source[cend + 1:]
        new_src, _ = _rewrite_import(new_src, bool(state))
        findings.append(Finding("REACT_CLASS_COMPONENT", "medium", line_of(m.start()),
                                f"Class component '{name}' converted to a function component", True))
        for k in state:
            findings.append(Finding("REACT_STATE_TO_HOOK", "low", line_of(m.start()),
                                    f"State '{k}' -> const [{k}, {_setter(k)}] = useState(...)", True))
        for n in dict.fromkeys(notes):
            findings.append(Finding("REACT_SETSTATE_FUNCTIONAL", "low", line_of(m.start()), n, True))
        return make_result(source, new_src, findings)
    except Unsupported as exc:
        findings.append(Finding("REACT_UNSUPPORTED", "high", line_of(m.start()), str(exc), review_required=True))
        return make_result(source, None, findings)


def validate(source: str):
    """Parse JS/JSX with @babel/parser (node). Reports could_not_run honestly."""
    script = os.path.join(TOOLS, "check_syntax.js")
    if not os.path.isdir(os.path.join(TOOLS, "node_modules", "@babel", "parser")):
        return [{"check": "jsx_syntax", "status": "could_not_run", "detail": "@babel/parser not installed (run npm install in backend/tools)"}]
    try:
        p = subprocess.run(["node", script], input=source, capture_output=True, text=True, timeout=20)
        out = json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return [{"check": "jsx_syntax", "status": "could_not_run", "detail": f"node unavailable: {exc}"}]
    if out.get("ok"):
        return [{"check": "jsx_syntax", "status": "passed", "detail": "@babel/parser accepted the output"}]
    return [{"check": "jsx_syntax", "status": "failed", "detail": out.get("error", "parse error")}]
