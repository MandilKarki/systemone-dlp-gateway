# systemone-dlp-gateway

> A policy-first DLP gateway for AI agents: classify PII, assess egress risk, and triage sensitive transfers using Jev, local decision-model adapters, and deterministic enforcement rules.

## Jev DLP decision-gate prototype

This prototype combines Jev with a local, Apache-2.0 open model (Mistral Small
3.1 via Ollama) between deterministic DLP detection and an agent's egress tool.
It does **not** send a complete document to any model: the caller sends minimal,
redacted evidence and metadata. The gate returns one of `allow`,
`review`, or `block` and emits an auditable JSON record.

## Architecture

`agent/tool request -> deterministic detectors -> Jev typed judgement -> local policy -> allow | review | block`

Deterministic policy is the authority: secrets are blocked without asking a
model, and any API error or low-confidence decision becomes `review`.

## Run

Requires Python 3.11+ and no third-party packages.

```powershell
python benchmark.py
```

## Test console

The React console keeps keys on the Python service, never in browser JavaScript.

```powershell
python server.py
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The provider options are
the same as the benchmark: rules, Jev, local Ollama/Mistral, and conservative
Jev-plus-local consensus. For a distributable local console, run `npm run build`
and use `python server.py` to serve `frontend/dist` at port 8000.

This runs the included 30-case synthetic, redacted regression corpus with the
deterministic adapter. To evaluate the actual Jev API, set a key and opt in:

```powershell
$env:TYPESAFE_API_KEY = "..."
python benchmark.py --provider jev
```

For the local open-model comparison, install Ollama and pull the model (about
15 GB), then run the local or consensus lane. `DLP_OLLAMA_MODEL` can select a
different locally installed non-Chinese Ollama model.

```powershell
ollama pull mistral-small3.1
python benchmark.py --provider ollama
python benchmark.py --provider ensemble
```

`ensemble` uses Jev and local Mistral. Any model disagreement or provider error
becomes `review`; it never becomes an allow or a block purely from disagreement.

The Jev endpoint is `POST https://api.typesafe.ai/v1/systemone`.  The runner
does not put the key in source code or logs. Results are written to
`outputs/benchmark-<provider>.json`.

## Benchmark protocol

Compare `--provider deterministic`, `--provider ollama`, `--provider jev`, and
`--provider ensemble` on the exact same frozen corpus. Report: unsafe-allow rate (primary), block precision/recall,
review rate, p50/p95 latency, and input tokens when returned by the API.
Before production, replace `corpus.jsonl` with a redacted, human-labelled holdout
set stratified by sensitive type, destination trust, and adversarial phrasing.

## Jev request shape

Each call asks one `choice` question for sensitivity, one `score` for exposure
risk, and one `noul` question for whether egress violates policy. The local
gate only blocks a model-labelled restricted transfer when its probability is
at least 0.90; otherwise it reviews. This threshold is intentionally a starting
point to calibrate against your own labels.
