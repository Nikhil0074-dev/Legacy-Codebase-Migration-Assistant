import pytest
from app.diffing import side_by_side, unified
from app.security import safe_filename, scan_secrets
from app.store import Store


def test_diff_rows_equal_change_insert_delete():
    rows = side_by_side("a\nb\nc\n", "a\nB\nc\nd\n")
    assert [r["tag"] for r in rows] == ["equal", "change", "equal", "insert"]
    assert rows[1]["left"] == "b" and rows[1]["right"] == "B"
    assert rows[3]["ln"] is None and rows[3]["rn"] == 4


def test_diff_delete():
    assert [r["tag"] for r in side_by_side("a\nb\n", "a\n")] == ["equal", "delete"]


def test_identical_files_have_no_changes():
    assert all(r["tag"] == "equal" for r in side_by_side("x\n", "x\n"))


def test_unified_diff_headers():
    assert unified("a\n", "b\n", "f.py").startswith("--- a/f.py\n+++ b/f.py")


@pytest.mark.parametrize("bad", ["../x.py", "a/b.py", "..\\x.py", "/etc/passwd", ".env", "a\x00.py", "", "x" * 300, "we ird$.py"])
def test_unsafe_filenames_rejected(bad):
    with pytest.raises(ValueError):
        safe_filename(bad)


def test_safe_filename_ok():
    assert safe_filename("my_file-1.py") == "my_file-1.py"


def test_secret_scan_reports_lines_not_values():
    hits = scan_secrets('x = 1\naws = "AKIAABCDEFGHIJKLMNOP"\npassword = "hunter2hunter2"\n')
    assert ("AWS access key", 2) in hits and any(h[1] == 3 for h in hits)
    assert all("AKIA" not in str(h) for h in hits)


def test_no_false_secret_on_plain_code():
    assert scan_secrets("token_count = 5\nprint('hi')\n") == []


def test_store_roundtrip_and_ordering():
    s = Store()
    s.save({"id": "a", "v": 1}); s.save({"id": "b", "v": 2}); s.save({"id": "a", "v": 3})
    assert s.get("a")["v"] == 3 and s.get("zzz") is None
    assert [j["id"] for j in s.list()] == ["b", "a"]
