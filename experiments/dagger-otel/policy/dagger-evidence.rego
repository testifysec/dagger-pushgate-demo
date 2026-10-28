package dagger_check_evidence

# Reads dagger-evidence.json, the converter's output from Dagger's OpenTelemetry
# trace (no text scraping of the progress report). Two carriers, same document:
#   - structured-data/v0.1 predicate `data` (--attestor-structured-data-embed-data).
#     cilock exports it as its own statement, which `cilock verify` does not load
#     into a step today (see RESULTS.md), so
#   - command-run/v0.2 `stdout`: pipeline.sh prints the file as its only stdout.
#     This is the carrier the verified policy uses.

pred := object.get(input, "attestation", input)

doc := d {
	d := pred.data
	is_object(d)
} else := d {
	is_string(pred.stdout)
	d := json.unmarshal(pred.stdout)
} else := null

deny[msg] {
	is_number(pred.exitcode)
	pred.exitcode != 0
	msg := sprintf("wrapped command exited %v", [pred.exitcode])
}

schema := "https://testifysec.com/alps/dagger-check-evidence/v0"

go_test_check := "go/packages/tests/test"

# The tests this repo must run. Pinned in the policy, not read from dagger.toml,
# so a dagger.toml filter cannot shrink the set.
required_tests := {
	"TestParse", "TestParseRejects", "TestSpecOrdering", "TestBuildMetadataIgnored",
	"TestNumericBeforeAlphanumeric", "TestMajorDominates", "TestSuiteLoad",
}

deny[msg] {
	not is_object(doc)
	msg := "unreadable evidence: no embedded dagger-evidence data"
}

deny[msg] {
	is_object(doc)
	doc.schema != schema
	msg := sprintf("unexpected evidence schema %v", [doc.schema])
}

deny[msg] {
	is_object(doc)
	doc.exit_code != 0
	msg := sprintf("dagger check exited %v", [doc.exit_code])
}

deny[msg] {
	is_object(doc)
	count(doc.checks) == 0
	msg := "dagger check ran zero checks"
}

deny[msg] {
	c := doc.checks[_]
	not c.passed
	msg := sprintf("check failed: %v (%v)", [c.check, c.status])
}

deny[msg] {
	t := doc.tests[_]
	t.status != "pass"
	msg := sprintf("test %v %v: %v", [t.suite, t.name, t.status])
}

deny[msg] {
	l := doc.listed[_]
	count(l.covered_by) == 0
	msg := sprintf("listed check did not run: %v", [l.link])
}

# Tests that a passing go test check selected.
ran_tests[t] {
	c := doc.checks[_]
	c.check == go_test_check
	c.passed
	t := c.params["go-test"][_]
}

deny[msg] {
	is_object(doc)
	missing := required_tests - ran_tests
	count(missing) > 0
	msg := sprintf("required tests not run by a passing go test check: %v", [sort(missing)])
}

# A go test check that actually executed must report per-test results; one that was
# a cache hit reports none (the trace carries no test spans then), so it must carry an
# input key that earlier evidence can be matched on.
deny[msg] {
	c := doc.checks[_]
	c.check == go_test_check
	not c.cached
	count(c.tests) == 0
	msg := "go test check executed but the trace has no per-test results"
}

deny[msg] {
	c := doc.checks[_]
	c.check == go_test_check
	not is_string(c.engine_key)
	msg := "go test check has no engine cache key"
}

deny[msg] {
	c := doc.checks[_]
	not is_string(c.input_key)
	msg := sprintf("check %v has no input digest", [c.check])
}
