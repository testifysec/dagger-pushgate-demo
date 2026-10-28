#!/usr/bin/env python3
"""Convert a Dagger `dagger check` OTLP trace into a JSON evidence document.

usage: dagger_otel_evidence.py <traces.jsonl> [--listed listed.txt] [--exit N] > evidence.json

<traces.jsonl>  one OTLP ExportTraceServiceRequest (protobuf JSON mapping) per line,
                as written by otlp_receiver.py.
--listed        output of `dagger check -l --all -f link` from the same workspace.
--exit          exit code of the `dagger check` process.

This reads; it never signs. cilock records the output file (structured-data attestor).
Tested against Dagger v1.0.0-beta.19 with the dagger.io/go module v0.3.1.

Span fields used (all set by the engine or the CLI, see RESULTS.md):
  check span        attrs dagger.io/check.name, dagger.io/check.passed; status.code
  cache outcome     attrs dagger.io/cache.outcome (hit|executed|uncached|joined),
                    dagger.io/cache.hit.route, dagger.io/dag.digest, dagger.io/dag.call
  real execution    spans named exec.run / exec.processRun (attr wcprof.exec.argv)
  host inputs       Host/Workspace.directory spans: dagger.io/dag.content_preferred_digest (sha256)
  per-test results  attrs test.suite.name, test.case.name, test.case.result.status
                    (pass only; a failed case has span status ERROR instead), emitted by
                    otelgotest inside the test container
"""
import base64, hashlib, json, sys
from urllib.parse import parse_qsl, urlsplit

SCHEMA = "https://testifysec.com/alps/dagger-check-evidence/v0"


def val(v):
    for k in ("stringValue", "boolValue", "doubleValue"):
        if k in v:
            return v[k]
    if "intValue" in v:
        return int(v["intValue"])
    if "arrayValue" in v:
        return [val(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {x["key"]: val(x["value"]) for x in v["kvlistValue"].get("values", [])}
    return None


def load_spans(path):
    spans = {}
    for line in open(path):
        for rs in json.loads(line).get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                for s in ss.get("spans", []):
                    d = {
                        "id": s["spanId"], "trace": s["traceId"], "parent": s.get("parentSpanId"),
                        "name": s["name"],
                        "start": int(s.get("startTimeUnixNano", 0)),
                        "end": int(s.get("endTimeUnixNano", 0)),
                        "status": s.get("status", {}).get("code", "STATUS_CODE_UNSET"),
                        "attrs": {a["key"]: val(a["value"]) for a in s.get("attributes", [])},
                    }
                    prev = spans.get(d["id"])
                    if prev is None or d["end"] >= prev["end"]:
                        spans[d["id"]] = d
    return spans


# --- minimal protobuf wire reader, enough to pull argv out of dagger.io/dag.call ---
def _varint(b, i):
    x = s = 0
    while True:
        c = b[i]; i += 1
        x |= (c & 0x7F) << s; s += 7
        if c < 0x80:
            return x, i


def _fields(b):
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
        elif wt == 2:
            n, i = _varint(b, i); v = b[i:i + n]; i += n
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError("wire type %d" % wt)
        if i > len(b) or f == 0:
            raise ValueError("truncated")
        yield f, wt, v


def _literal(b):
    """Decode a dagger callpbv1.Literal: 7 = string, 8 = List{1: repeated Literal}."""
    for f, wt, v in _fields(b):
        if f == 7 and wt == 2:
            return v.decode()
        if f == 8 and wt == 2:
            return [_literal(x) for lf, lwt, x in _fields(v) if lf == 1 and lwt == 2]
    return None


def call_argv(attrs):
    """argv of a Container.withExec call, from the 'args' argument of dag.call."""
    raw = attrs.get("dagger.io/dag.call")
    if not raw:
        return None
    b = base64.b64decode(raw)
    try:
        for f, wt, v in _fields(b):  # Call.args = field 4 (Argument{name=1, value=2})
            if f == 4 and wt == 2:
                arg = list(_fields(v))
                name = next((x[2].decode() for x in arg if x[0] == 1), None)
                if name == "args":
                    value = next((x[2] for x in arg if x[0] == 2), b"")
                    return _literal(value)
    except Exception:
        return None
    return None


def parse_link(link):
    q = urlsplit(link.replace("dag+check://", "dag://")).query
    params = {}
    for k, v in parse_qsl(q, keep_blank_values=True):
        params.setdefault(k, []).append(v)
    return params.pop("check", [""])[0], params


def convert(spans, listed=None, exit_code=None):
    kids = {}
    for s in spans.values():
        kids.setdefault(s["parent"], []).append(s)

    def desc(sid):
        for c in kids.get(sid, []):
            yield c
            yield from desc(c["id"])

    roots = [s for s in spans.values() if not s["parent"] or s["parent"] not in spans]
    root = max(roots, key=lambda s: s["end"] - s["start"]) if roots else None

    checks = []
    for s in sorted(spans.values(), key=lambda s: s["start"]):
        name = s["attrs"].get("dagger.io/check.name")
        if name is None:
            continue
        path, params = parse_link(name)
        execs, ran, inputs, tests = [], [], set(), []
        for d in desc(s["id"]):
            a = d["attrs"]
            if d["name"] == "Container.withExec" and "dagger.io/cache.outcome" in a:
                execs.append({
                    "digest": a.get("dagger.io/dag.digest"),
                    "argv": call_argv(a),
                    "outcome": a["dagger.io/cache.outcome"],
                    "hit_route": a.get("dagger.io/cache.hit.route"),
                })
            if d["name"] == "exec.processRun":
                ran.append(json.loads(a["wcprof.exec.argv"]) if "wcprof.exec.argv" in a else None)
            cd = a.get("dagger.io/dag.content_preferred_digest", "")
            if cd.startswith("sha256:"):  # only directories read from the host carry sha256
                inputs.add(cd)
            if "test.case.name" in a:
                # a passing case carries test.case.result.status=pass; a failing one
                # (dagger.io/go v0.3.1) carries no result status, only span status ERROR
                # and test.suite.run.status=failure
                status = a.get("test.case.result.status")
                if status is None:
                    status = "fail" if d["status"] == "STATUS_CODE_ERROR" else "unknown"
                tests.append({"suite": a.get("test.suite.name"), "name": a["test.case.name"],
                              "status": status, "span_status": d["status"]})
        inputs = sorted(inputs)
        # engine_key: the engine's own cache digest for the exec that runs the check's
        # command. dagger.io/go runs tests as `otelgotest <pkg>`; other checks run no
        # exec of their own, so they get none.
        runner = [e for e in execs if e["argv"] and e["argv"][0] == "otelgotest"]
        checks.append({
            "name": name,
            "check": path,
            "params": params,
            "passed": s["attrs"].get("dagger.io/check.passed") is True and s["status"] != "STATUS_CODE_ERROR",
            "status": s["status"],
            "duration_ms": round((s["end"] - s["start"]) / 1e6),
            "cached": len(ran) == 0,
            "executed_processes": ran,
            "input_digests": inputs,
            "input_key": "sha256:" + hashlib.sha256("\n".join(inputs).encode()).hexdigest() if inputs else None,
            "engine_key": runner[-1]["digest"] if runner else None,
            "execs": execs,
            "tests": sorted(tests, key=lambda t: t["name"]),
        })

    coverage = None
    if listed is not None:
        coverage = []
        for link in listed:
            lp, lparams = parse_link(link)
            by = [c["name"] for c in checks if c["check"] == lp and all(
                set(v) <= set(c["params"].get(k, [])) for k, v in lparams.items())]
            coverage.append({"link": link, "covered_by": by})

    tests = [dict(t, check=c["check"]) for c in checks for t in c["tests"]]
    return {
        "schema": SCHEMA,
        "producer": {"tool": "dagger", "trace_ids": sorted({s["trace"] for s in spans.values()}),
                     "root_span": root["name"] if root else None,
                     "root_status": root["status"] if root else None},
        "exit_code": exit_code,
        "listed": coverage,
        "checks": checks,
        "tests": tests,
        "summary": {
            "checks": len(checks),
            "checks_failed": sum(not c["passed"] for c in checks),
            "checks_cached": sum(c["cached"] for c in checks),
            "tests": len(tests),
            "tests_failed": sum(t["status"] != "pass" for t in tests),
            "listed_uncovered": sum(not x["covered_by"] for x in coverage) if coverage is not None else None,
        },
    }


def main(argv):
    path, listed, code = argv[1], None, None
    if "--listed" in argv:
        listed = [l.strip() for l in open(argv[argv.index("--listed") + 1]) if l.startswith("dag")]
    if "--exit" in argv:
        code = int(argv[argv.index("--exit") + 1])
    json.dump(convert(load_spans(path), listed, code), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv)
