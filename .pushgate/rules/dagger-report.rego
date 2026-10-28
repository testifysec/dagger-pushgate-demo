package dagger_report

# Reads the report `dagger check --progress report` writes to stderr, which
# cilock's command-run attestor records. Dagger 1.0.0-beta.19's Go module
# writes no JUnit, so the stock tests-pass rule has nothing to read.

pred := object.get(input, "attestation", input)

report := object.get(pred, "stderr", null)

deny[msg] {
	not is_string(report)
	msg := "unreadable evidence: command-run recorded no stderr"
}

deny[msg] {
	is_string(report)
	not contains(report, "== TRACE ==  ✔ PASSED")
	msg := "dagger report does not say the run PASSED"
}

deny[msg] {
	is_string(report)
	regex.match(`== CHECKS ==[^\n]*failed`, report)
	msg := "dagger report lists a failed check"
}

# A dagger.toml that filters the tests out (test = ["!**"]) still exits 0,
# so require the Go test check itself to appear and pass.
deny[msg] {
	is_string(report)
	not go_tests_passed
	msg := "no passing go test check in the dagger report"
}

go_tests_passed {
	line := split(report, "\n")[_]
	startswith(line, "✔ dag://?check=go/packages/tests/test")
	endswith(line, " OK")
}
