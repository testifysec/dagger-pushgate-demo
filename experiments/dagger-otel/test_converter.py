#!/usr/bin/env python3
"""Converter tests against real traces captured from Dagger v1.0.0-beta.19 (fixtures/).
run: python3 test_converter.py"""
import gzip, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dagger_otel_evidence as m

F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
TESTS = {"TestParse", "TestParseRejects", "TestSpecOrdering", "TestBuildMetadataIgnored",
         "TestNumericBeforeAlphanumeric", "TestMajorDominates", "TestSuiteLoad"}


def load(name, code):
    with tempfile.NamedTemporaryFile("wb", suffix=".jsonl", delete=False) as t:
        t.write(gzip.open(f"{F}/{name}.traces.jsonl.gz").read())
    listed = [l.strip() for l in open(f"{F}/{name}.listed.txt") if l.startswith("dag")]
    return m.convert(m.load_spans(t.name), listed, code)


def gotest(d):
    return [c for c in d["checks"] if c["check"] == "go/packages/tests/test"]


cold, warm = load("e1-cold", 0), load("e1-warm", 0)
for d in (cold, warm):
    assert d["summary"]["checks"] == 2 and d["summary"]["checks_failed"] == 0
    assert d["summary"]["listed_uncovered"] == 0 and len(d["listed"]) == 9
    assert all(c["input_key"].startswith("sha256:") for c in d["checks"])
(c,), (w,) = gotest(cold), gotest(warm)
assert not c["cached"] and w["cached"]
assert {t["name"] for t in c["tests"] if t["status"] == "pass"} == TESTS
assert w["tests"] == []
assert c["engine_key"] == w["engine_key"] and c["input_key"] == w["input_key"]
assert ["otelgotest", "./semver"] in c["executed_processes"] and w["executed_processes"] == []

fail = load("neg-fail", 1)
(f,) = gotest(fail)
assert not f["passed"] and f["status"] == "STATUS_CODE_ERROR"
assert [t["name"] for t in f["tests"] if t["status"] == "fail"] == ["TestMajorDominates"]

zero = load("neg-zero", 1)
assert zero["checks"] == [] and zero["producer"]["root_status"] == "STATUS_CODE_ERROR"

# argv decoding of dag.call (Literal list of strings)
assert ["go-includes", "--all", "--output-dir", "/output", "--test"] in [e["argv"] for e in c["execs"]]
print("ok")
