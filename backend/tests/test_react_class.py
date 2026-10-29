import os
import pytest
from app.migration import react_class as r

COUNTER = open("../sample-projects/react-class-components/Counter.jsx").read()
HAS_BABEL = os.path.isdir(os.path.join(r.TOOLS, "node_modules", "@babel", "parser"))


def test_counter_converted():
    res = r.migrate(COUNTER)
    out = res["migrated"]
    assert "function Counter()" in out
    assert "const [count, setCount] = useState(0);" in out
    assert "setCount((prevCount) => prevCount + 1)" in out
    assert "class " not in out and "this." not in out
    assert "export default Counter;" in out
    assert res["status"] == "safe"


def test_import_rewritten_with_usestate():
    out = r.migrate(COUNTER)["migrated"]
    assert 'import React, { useState } from "react";' in out


def test_named_component_import_removed_and_hooks_added():
    src = COUNTER.replace('import React from "react";', 'import React, { Component } from "react";')
    assert "Component" not in r.migrate(src)["migrated"].split("\n")[0]


@pytest.mark.skipif(not HAS_BABEL, reason="@babel/parser not installed")
def test_counter_output_parses_with_babel():
    assert r.validate(r.migrate(COUNTER)["migrated"])[0]["status"] == "passed"


@pytest.mark.skipif(not HAS_BABEL, reason="@babel/parser not installed")
def test_babel_detects_invalid_syntax():
    assert r.validate("function (")[0]["status"] == "failed"


def test_profile_sample_multi_key_state_and_props():
    src = open("../sample-projects/react-class-components/Profile.jsx").read()
    res = r.migrate(src)
    out = res["migrated"]
    assert "export default function Profile(props)" in out
    assert "const [editing, setEditing] = useState(false);" in out
    assert 'const [name, setName] = useState("Ada");' in out
    assert "setName(event.target.value);\n    setEditing(false);" in out
    assert "setEditing((prevEditing) => !prevEditing)" in out
    assert "Don't forget" in out and "this." not in out


def test_lifecycle_requires_manual_review():
    src = open("../sample-projects/react-class-components/Timer.jsx").read()
    res = r.migrate(src)
    assert res["migrated"] is None and res["status"] == "manual_review_required"
    rules = [f["rule_id"] for f in res["findings"]]
    assert rules.count("REACT_LIFECYCLE") == 2


def test_pure_component_not_converted():
    src = "class A extends React.PureComponent { render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_no_class_means_no_changes():
    res = r.migrate("const A = () => null;\n")
    assert res["status"] == "no_changes"


def test_setstate_callback_needs_review():
    src = "class A extends React.Component { state = {a: 1}; f = () => { this.setState({a: 2}, () => {}); }; render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_setstate_updater_function_needs_review():
    src = "class A extends React.Component { state = {a: 1}; f = () => { this.setState(s => ({a: s.a})); }; render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_unknown_state_key_needs_review():
    src = "class A extends React.Component { state = {a: 1}; f = () => { this.setState({b: 2}); }; render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_constructor_logic_beyond_state_needs_review():
    src = "class A extends React.Component { constructor(p){ super(p); this.state={a:1}; this.x = fetch(); } render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_instance_field_use_needs_review():
    src = "class A extends React.Component { state={a:1}; f = () => { this.timer = 1; }; render() { return null; } }"
    assert r.migrate(src)["migrated"] is None


def test_multiple_classes_need_review():
    src = "class A extends React.Component { render(){return null;} }\nclass B extends React.Component { render(){return null;} }"
    assert r.migrate(src)["migrated"] is None


def test_bind_calls_in_constructor_removed():
    src = ('class A extends React.Component {\n constructor(p){ super(p); this.state={n:0}; this.inc = this.inc.bind(this); }\n'
           ' inc() { this.setState({n: this.state.n + 1}); }\n render(){ return <b onClick={this.inc}>{this.state.n}</b>; }\n}')
    out = r.migrate(src)["migrated"]
    assert "bind" not in out and "function inc()" in out and "onClick={inc}" in out


def test_stateless_class_converted_without_hooks():
    src = 'import React from "react";\nclass Hi extends React.Component {\n  render() {\n    return <p>{this.props.name}</p>;\n  }\n}\n'
    out = r.migrate(src)["migrated"]
    assert "function Hi(props)" in out and "props.name" in out and "useState" not in out


def test_findings_report_locations():
    res = r.migrate(COUNTER)
    cls = [f for f in res["findings"] if f["rule_id"] == "REACT_CLASS_COMPONENT"][0]
    assert cls["line"] == 3 and cls["auto_fixed"]


def test_migration_is_idempotent():
    once = r.migrate(COUNTER)["migrated"]
    assert r.migrate(once)["status"] == "no_changes"


def test_find_close_ignores_braces_in_strings_and_comments():
    s = '{ a = "}"; // }\n /* } */ b }'
    assert r.find_close(s, 0) == len(s) - 1
