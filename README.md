# dagger-pushgate-demo

A small Go library (`semver`) whose tests run under [Dagger](https://dagger.io)
1.0 and whose pushes go through [Pushgate](https://pushgate.dev).

The developer loop:

```sh
git commit -am "..."
cilock run --step dagger-check -- dagger check --progress report
git push
```

`cilock run` wraps `dagger check`, records what ran and what it printed, and
signs that record for the commit. Pushgate admits the push only when the signed
record satisfies `.pushgate/policy.json`:

| Rule | Refuses |
|---|---|
| `command-succeeded` | a `dagger check` that exited non-zero |
| `command-pin` | any argv other than `dagger check --progress report` |
| `dagger-report-pass` | a report with no passing Go test check, e.g. a `dagger.toml` that filters the tests out |

The `dagger-report-pass` source is `.pushgate/rules/dagger-report.rego`; the
policy embeds it base64-encoded.

Tested with Dagger v1.0.0-beta.19 and the `dagger.io/go` module v0.3.1.
