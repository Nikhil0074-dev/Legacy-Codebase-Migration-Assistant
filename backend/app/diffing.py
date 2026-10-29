"""Side-by-side and unified diff generation."""
import difflib


def side_by_side(a: str, b: str):
    al, bl = a.splitlines(), b.splitlines()
    rows = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                rows.append({"tag": "equal", "ln": i1 + k + 1, "left": al[i1 + k], "rn": j1 + k + 1, "right": bl[j1 + k]})
            continue
        for k in range(max(i2 - i1, j2 - j1)):
            has_l, has_r = k < i2 - i1, k < j2 - j1
            rows.append({
                "tag": "change" if has_l and has_r else ("delete" if has_l else "insert"),
                "ln": i1 + k + 1 if has_l else None, "left": al[i1 + k] if has_l else "",
                "rn": j1 + k + 1 if has_r else None, "right": bl[j1 + k] if has_r else "",
            })
    return rows


def unified(a: str, b: str, name: str):
    return "".join(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{name}", f"b/{name}"))
