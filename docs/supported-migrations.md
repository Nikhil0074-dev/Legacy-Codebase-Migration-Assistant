# Supported migrations

## python2-to-python3 (`.py`)
Auto-fixed: `print` statements → `print()`; `raw_input` → `input`; `xrange` → `range`; `except X, e` → `except X as e`; `.iteritems/.itervalues/.iterkeys()` → `.items/.values/.keys()`; `<>` → `!=`.
Reported for review (never rewritten): `/` division, `print >>f`, print with trailing comma, `raise E, msg`, `exec`, backticks, `has_key`, `unicode/basestring/long/unichr/reduce/execfile/cmp`, renamed stdlib modules (`urllib2`, `ConfigParser`, `Queue`, `cPickle`, `StringIO`, `urlparse`, `Tkinter`).
Strings and comments are never modified (tokenizer-based).

## react-class-to-function (`.jsx`, `.js`, `.tsx`)
Converted: one class per file; state from constructor or class property → one `useState` per key; arrow/regular methods → inner functions; `this.props` → `props`; `this.setState({...})` with object literals (functional update when the new value reads the same key); `.bind(this)` lines removed; React import rewritten.
Left for a human (file reported as `manual_review_required`): lifecycle methods, `PureComponent`, `setState` updater functions or callbacks, instance fields/refs, static/getter members, constructor logic, multiple classes.

## Not implemented (proposal items intentionally out of scope)
JavaScript→TypeScript typing, PHP, React Server Components, AI-assisted proposals, hunk-level accept/reject, regression-test *generation*, running the target project's own tests in a sandbox, authentication, Monaco editor (a lightweight built-in diff view is used so the UI works offline).
