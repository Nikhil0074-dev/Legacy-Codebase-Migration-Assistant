import pytest
from fastapi.testclient import TestClient
from app.main import create_app

PY = open("../sample-projects/legacy-python/simple_script.py").read()
JSX = open("../sample-projects/react-class-components/Counter.jsx").read()
TIMER = open("../sample-projects/react-class-components/Timer.jsx").read()


@pytest.fixture()
def c():
    return TestClient(create_app(":memory:"))


def create(c, name, content, mt):
    return c.post("/api/migrations", json={"filename": name, "content": content, "migration_type": mt})


def test_health_and_types(c):
    assert c.get("/api/health").json() == {"status": "ok"}
    assert {t["id"] for t in c.get("/api/migration-types").json()} == {"python2-to-python3", "react-class-to-function"}


def test_samples_endpoint(c):
    names = {s["name"] for s in c.get("/api/samples").json()}
    assert {"legacy_app.py", "Counter.jsx", "Timer.jsx"} <= names


def test_full_python_workflow(c):
    r = create(c, "simple_script.py", PY, "python2-to-python3")
    assert r.status_code == 201
    job = r.json(); jid = job["id"]
    assert job["migrated"] == 'name = input("Enter your name: ")\nprint("Hello", name)\n'
    assert job["original"] == PY and job["review"] == "pending"
    assert c.get(f"/api/migrations/{jid}/findings").json()
    d = c.get(f"/api/migrations/{jid}/diff").json()
    assert d["available"] and any(row["tag"] == "change" for row in d["rows"]) and "+++ b/simple_script.py" in d["unified"]
    assert c.get(f"/api/migrations/{jid}/tests").json()["validation"][0]["status"] == "passed"
    assert c.get(f"/api/migrations/{jid}/export").status_code == 409      # not yet accepted
    assert c.post(f"/api/migrations/{jid}/review", json={"decision": "accept"}).json()["review"] == "accepted"
    ex = c.get(f"/api/migrations/{jid}/export")
    assert ex.status_code == 200 and ex.text == job["migrated"] and "attachment" in ex.headers["content-disposition"]
    rep = c.get(f"/api/migrations/{jid}/report").text
    assert "Migration report" in rep and "accepted" in rep and "never executed" in rep
    assert c.get(f"/api/migrations/{jid}").json()["original"] == PY      # original preserved


def test_reject_keeps_original_and_blocks_export(c):
    jid = create(c, "a.py", PY, "python2-to-python3").json()["id"]
    assert c.post(f"/api/migrations/{jid}/review", json={"decision": "reject"}).json()["review"] == "rejected"
    assert c.get(f"/api/migrations/{jid}/export").status_code == 409
    assert c.get(f"/api/migrations/{jid}").json()["original"] == PY


def test_react_workflow(c):
    job = create(c, "Counter.jsx", JSX, "react-class-to-function").json()
    assert "useState" in job["migrated"] and job["migration_status"] == "safe"


def test_lifecycle_file_cannot_be_accepted(c):
    job = create(c, "Timer.jsx", TIMER, "react-class-to-function").json()
    assert job["migrated"] is None and job["migration_status"] == "manual_review_required"
    assert c.get(f"/api/migrations/{job['id']}/diff").json()["available"] is False
    assert c.post(f"/api/migrations/{job['id']}/review", json={"decision": "accept"}).status_code == 409
    assert c.post(f"/api/migrations/{job['id']}/validate").status_code == 409


def test_invalid_output_is_marked_failed_and_not_acceptable(c, monkeypatch):
    from app.services import migration_service as svc
    monkeypatch.setitem(svc.REGISTRY["python2-to-python3"], "migrate",
                        lambda s: {"migrated": "print 'x'\n", "findings": [], "status": "safe"})
    job = create(c, "a.py", PY, "python2-to-python3").json()
    assert job["migration_status"] == "failed"
    assert c.post(f"/api/migrations/{job['id']}/review", json={"decision": "accept"}).status_code == 409


def test_revalidate_endpoint(c):
    jid = create(c, "a.py", PY, "python2-to-python3").json()["id"]
    assert c.post(f"/api/migrations/{jid}/validate").json()[0]["status"] == "passed"


def test_listing_history_newest_first(c):
    a = create(c, "a.py", PY, "python2-to-python3").json()["id"]
    b = create(c, "b.py", PY, "python2-to-python3").json()["id"]
    assert [j["id"] for j in c.get("/api/migrations").json()] == [b, a]
    c.post(f"/api/migrations/{a}/review", json={"decision": "accept"})
    assert [h["event"] for h in c.get(f"/api/migrations/{a}").json()["history"]][-1] == "review: accepted"


def test_unknown_id_404(c):
    for path in ("", "/findings", "/diff", "/report", "/export", "/tests"):
        assert c.get(f"/api/migrations/nope{path}").status_code == 404
    assert c.post("/api/migrations/nope/review", json={"decision": "accept"}).status_code == 404


def test_rejects_unknown_type_ext_and_bad_decision(c):
    assert create(c, "a.py", PY, "cobol-to-rust").status_code == 400
    assert create(c, "a.php", PY, "python2-to-python3").status_code == 400
    jid = create(c, "a.py", PY, "python2-to-python3").json()["id"]
    assert c.post(f"/api/migrations/{jid}/review", json={"decision": "maybe"}).status_code == 422
