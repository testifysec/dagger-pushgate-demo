#!/usr/bin/env python3
"""Minimal local OTLP/HTTP receiver. Writes each export request as one JSON line.

usage: otlp_receiver.py <outdir> [port]
  <outdir>/traces.jsonl, logs.jsonl, metrics.jsonl
Accepts application/x-protobuf (optionally gzip) and application/json.
Listens on 127.0.0.1 only. Nothing leaves the machine.
"""
import gzip, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from google.protobuf.json_format import MessageToDict, Parse
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2 as ts
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2 as ls
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2 as ms

OUT = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 4318
KINDS = {
    "/v1/traces": ("traces", ts.ExportTraceServiceRequest, ts.ExportTraceServiceResponse),
    "/v1/logs": ("logs", ls.ExportLogsServiceRequest, ls.ExportLogsServiceResponse),
    "/v1/metrics": ("metrics", ms.ExportMetricsServiceRequest, ms.ExportMetricsServiceResponse),
}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        kind = KINDS.get(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        if not kind:
            self.send_response(404); self.end_headers(); return
        name, req_t, resp_t = kind
        req = req_t()
        if "json" in (self.headers.get("Content-Type") or ""):
            Parse(body, req)
        else:
            req.ParseFromString(body)
        with open(os.path.join(OUT, name + ".jsonl"), "a") as f:
            f.write(json.dumps(MessageToDict(req)) + "\n")
        out = resp_t().SerializeToString()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


os.makedirs(OUT, exist_ok=True)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
