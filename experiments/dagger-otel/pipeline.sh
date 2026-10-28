#!/bin/sh
# The command `cilock run` wraps. Run from the evidence directory (cilock's
# working directory), so the files written there become cilock products.
#   1. list the checks the workspace offers
#   2. dagger check, with the OpenTelemetry trace sent to the local receiver
#   3. convert the trace to dagger-evidence.json
# Its only stdout is dagger-evidence.json. It exits with dagger check's code.
# usage: pipeline.sh <workspace-dir>   (otlp_receiver.py must be listening, see README)
set -u
WS=$1
OUT=$(pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
TRACES=${DAGGER_OTEL_TRACES:-$HERE/.receiver/traces.jsonl}
rm -f "$TRACES"
(cd "$WS" && dagger check -l --all -f link -s) > "$OUT/listed.txt" 2> "$OUT/listed.err"
(cd "$WS" && OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318 OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
  dagger check --progress report) > "$OUT/check.stdout" 2> "$OUT/check.report"
rc=$?
mkdir -p "$OUT/raw" && mv "$TRACES" "$OUT/raw/traces.jsonl"
python3 "$HERE/dagger_otel_evidence.py" "$OUT/raw/traces.jsonl" --listed "$OUT/listed.txt" --exit $rc > "$OUT/dagger-evidence.json"
cat "$OUT/dagger-evidence.json"
exit $rc
