# Dagger trace as structured evidence (prototype)

`dagger check` exports an OpenTelemetry trace. This prototype turns that trace into a
JSON record that CI/lock signs and a policy reads as fields, instead of scraping the
text report on stderr (`.pushgate/rules/dagger-report.rego`).

It is a prototype: the converter is Python outside CI/lock, and the policy reads the
record from the command-run attestation's stdout because `cilock verify` does not yet
load the separate structured-data statement.

## What the record holds

Per check: name, pass/fail, whether it was served from cache, and `input_key`, a sha256
over the content digests of the directories the check read. On a run that executed the
tests, each Go test with its result.

## What we measured (28 October 2026)

Dagger v1.0.0-beta.19, `dagger.io/go` v0.3.1, engine on an Apple M2 Max in a 6-CPU,
8 GB colima VM. Suite padded to 30 s with `testdata/suite-seconds`.

| Run | Go test check | input_key | `dagger check` wall |
|---|---|---|---|
| cold | executed, 7/7 | `sha256:…` A | 31.70 s |
| rebased onto a README change (new commit) | cache hit | A (same) | 1.75 s |
| rebased onto a `semver/` change | executed, 7/7 | B | 31.61 s |

The policy (`policy/dagger-evidence.rego`, tests in `policy/dagger-evidence_test.rego`)
admits the cold and warm runs and refuses a failing test, a `dagger.toml` that filters
the tests out, and a run with zero checks.

## Read before you build on it

- Bind evidence to `input_key`, not to Dagger's engine cache key. The engine key is a
  64-bit xxh3 hash and includes the checkout directory's name.
- A cached run has no per-test results. It is admissible only by matching its
  `input_key` to an earlier signed run that executed the tests.
- Test results are emitted from inside the test container, so the code under test can
  emit them. The signature says "this machine saw this trace", nothing more.
- The Go module builds its test runner from `github.com/dagger/otel-go/cmd/otelgotest@main`,
  unpinned.

## Run it

```sh
python3 experiments/dagger-otel/otlp_receiver.py experiments/dagger-otel/.receiver &   # needs opentelemetry-proto
mkdir -p /tmp/ev && cd /tmp/ev
cilock run --step dagger-check -- /path/to/repo/experiments/dagger-otel/pipeline.sh /path/to/repo
python3 /path/to/repo/experiments/dagger-otel/test_converter.py      # converter, on recorded fixtures
opa test --v0-compatible /path/to/repo/experiments/dagger-otel/policy # policy rules
```
