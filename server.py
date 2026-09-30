"""Local API for the DLP test console. Never expose TYPESAFE_API_KEY to the browser."""
from __future__ import annotations
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from dlp_gate import classify_and_triage, decide, deterministic_provider, ensemble_provider, jev_provider, ollama_provider

PROVIDERS = {"deterministic": deterministic_provider, "jev": jev_provider,
             "ollama": ollama_provider, "ensemble": ensemble_provider}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path("frontend/dist")), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/api/evaluate":
            self.send_error(404); return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100_000: raise ValueError("request must be 1–100,000 bytes")
            payload = json.loads(self.rfile.read(size))
            provider = PROVIDERS[payload.get("provider", "deterministic")]
            evidence = str(payload["evidence"])
            destination = payload.get("destination", "public")
            action = payload.get("action", "paste")
            dlp = decide(destination, action, evidence, provider)
            triage = classify_and_triage(evidence, provider)
            result = {"verdict":dlp.verdict, "sensitivity":dlp.sensitivity,
                      "probability":dlp.probability, "reason":dlp.reason, "triage":triage}
            body = json.dumps(result).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))
        except Exception as error:
            self.send_error(503, f"Evaluation unavailable: {type(error).__name__}")

if __name__ == "__main__":
    print("DLP Console API: http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
