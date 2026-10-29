import ast
import pytest
from app.migration import python2to3 as p


def mig(src):
    return p.migrate(src)


def test_print_single_and_multiple_args():
    assert mig('print "Hello", name\n')["migrated"] == 'print("Hello", name)\n'


def test_bare_print():
    assert mig("print\n")["migrated"] == "print()\n"


def test_print_inside_string_and_comment_untouched():
    src = 's = "print x"\n# print y\n'
    r = mig(src)
    assert r["migrated"] == src and r["status"] == "no_changes"


def test_print_after_colon():
    assert mig('if a: print "x"\n')["migrated"] == 'if a: print("x")\n'


def test_print_with_trailing_comment_keeps_comment():
    assert mig('print "a" # note\n')["migrated"] == 'print("a") # note\n'


def test_print_variable_named_print_not_changed():
    src = "print = 3\nx = print\n"
    assert mig(src)["migrated"] == src


def test_raw_input_and_xrange_renamed():
    out = mig("x = raw_input('a')\nfor i in xrange(3): pass\n")["migrated"]
    assert "input('a')" in out and "range(3)" in out and "raw_input" not in out and "xrange" not in out


def test_attribute_named_like_builtin_not_renamed():
    src = "obj.xrange(3)\n"
    assert mig(src)["migrated"] == src


def test_except_comma_to_as():
    out = mig("try:\n    pass\nexcept IOError, e:\n    pass\n")["migrated"]
    assert "except IOError as e:" in out


def test_except_tuple_comma():
    out = mig("try:\n    pass\nexcept (A, B), e:\n    pass\n")["migrated"]
    assert "except (A, B) as e:" in out


def test_dict_iter_methods():
    out = mig("for k in d.iterkeys(): pass\nd.itervalues()\nd.iteritems()\n")["migrated"]
    assert ".keys()" in out and ".values()" in out and ".items()" in out


def test_not_equal_operator():
    out = mig("if a <> b: pass\n")["migrated"]
    assert "a != b" in out


def test_print_chevron_flagged_not_changed():
    r = mig("print >>f, 'x'\n")
    assert r["migrated"] == "print >>f, 'x'\n"
    assert any(f["rule_id"] == "PY_PRINT_CHEVRON" for f in r["findings"])


def test_trailing_comma_print_flagged():
    r = mig("print 'a',\n")
    assert any(f["rule_id"] == "PY_PRINT_TRAILING_COMMA" for f in r["findings"])
    assert r["status"] == "needs_review"


def test_division_flagged_for_review():
    r = mig("x = a / b\n")
    assert r["status"] == "needs_review" and r["migrated"] == "x = a / b\n"
    assert any(f["rule_id"] == "PY_DIVISION" and f["review_required"] for f in r["findings"])


def test_legacy_import_and_removed_names_flagged():
    r = mig("import urllib2\nx = unicode('a')\n")
    rules = {f["rule_id"] for f in r["findings"]}
    assert {"PY_LEGACY_IMPORT", "PY_REMOVED_UNICODE"} <= rules


def test_raise_comma_flagged():
    r = mig("raise ValueError, 'bad'\n")
    assert any(f["rule_id"] == "PY_RAISE_COMMA" for f in r["findings"])


def test_output_is_valid_python3_for_realistic_file():
    src = open("../sample-projects/legacy-python/legacy_app.py").read()
    r = mig(src)
    ast.parse(r["migrated"])
    assert p.validate(r["migrated"])[0]["status"] == "passed"


def test_modern_python3_code_is_idempotent():
    src = 'print("hi")\nname = input("x")\n'
    r = mig(src)
    assert r["migrated"] == src and r["status"] == "no_changes"


def test_migration_is_idempotent_on_its_own_output():
    first = mig('print "a", b\nx = raw_input("q")\n')["migrated"]
    assert mig(first)["migrated"] == first


def test_untokenizable_source_requires_manual_review():
    r = mig("x = (1,\n")
    assert r["migrated"] is None and r["status"] == "manual_review_required"


def test_validate_reports_failure():
    v = p.validate("print 'x'\n")
    assert v[0]["status"] == "failed"


def test_findings_have_locations_and_severity():
    r = mig('\n\nprint "x"\n')
    f = r["findings"][0]
    assert f["line"] == 3 and f["severity"] in {"info", "low", "medium", "high"}
