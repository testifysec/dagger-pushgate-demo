package dagger_check_evidence

# Each negative fires on its own: start from a passing document and change one thing.
# Run: opa test --v0-compatible policy/

good_check := {
	"check": "go/packages/tests/test", "passed": true, "status": "STATUS_CODE_OK",
	"cached": false, "engine_key": "xxh3:0000000000000001", "input_key": "sha256:aa",
	"params": {"go-package": ["semver"], "go-test": [
		"TestParse", "TestParseRejects", "TestSpecOrdering", "TestBuildMetadataIgnored",
		"TestNumericBeforeAlphanumeric", "TestMajorDominates", "TestSuiteLoad",
	]},
	"tests": [{"name": "TestParse", "status": "pass"}],
}

good_doc := {
	"schema": "https://testifysec.com/alps/dagger-check-evidence/v0",
	"exit_code": 0, "checks": [good_check],
	"tests": [{"suite": "s", "name": "TestParse", "status": "pass"}],
	"listed": [{"link": "dag+check://?check=go/packages/tests/test", "covered_by": ["x"]}],
}

as_stdout(d) := {"exitcode": 0, "stdout": json.marshal(d)}

test_good_passes {
	count(deny) == 0 with input as as_stdout(good_doc)
}

test_good_passes_as_structured_data {
	count(deny) == 0 with input as {"data": good_doc}
}

test_failing_test_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/tests/0/status", "value": "fail"}])
	deny["test s TestParse: fail"] with input as as_stdout(d)
}

test_filtered_tests_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/checks/0/params/go-test", "value": ["TestParse"]}])
	some m
	deny[m] with input as as_stdout(d)
	startswith(m, "required tests not run")
}

test_zero_checks_denied_even_with_exit_0 {
	d := json.patch(good_doc, [{"op": "replace", "path": "/checks", "value": []}])
	deny["dagger check ran zero checks"] with input as as_stdout(d)
}

test_executed_without_test_results_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/checks/0/tests", "value": []}])
	deny["go test check executed but the trace has no per-test results"] with input as as_stdout(d)
}

test_cached_without_test_results_allowed {
	d := json.patch(good_doc, [
		{"op": "replace", "path": "/checks/0/tests", "value": []},
		{"op": "replace", "path": "/checks/0/cached", "value": true},
	])
	count(deny) == 0 with input as as_stdout(d)
}

test_no_engine_key_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/checks/0/engine_key", "value": null}])
	deny["go test check has no engine cache key"] with input as as_stdout(d)
}

test_uncovered_listed_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/listed/0/covered_by", "value": []}])
	deny["listed check did not run: dag+check://?check=go/packages/tests/test"] with input as as_stdout(d)
}

test_unreadable_denied {
	deny["unreadable evidence: no embedded dagger-evidence data"] with input as {"exitcode": 0}
}

test_no_input_key_denied {
	d := json.patch(good_doc, [{"op": "replace", "path": "/checks/0/input_key", "value": null}])
	deny["check go/packages/tests/test has no input digest"] with input as as_stdout(d)
}
