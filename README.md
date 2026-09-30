# systemone-dlp-gateway

> A model-only research gateway for evaluating Jev-style typed-decision models on DLP and agent-egress tasks.

This is a research prototype, **not a production DLP enforcement system**. One selected decision model receives destination, action, redacted evidence, and typed questions; it returns `allow`, `review`, or `block` plus sensitivity, PII type, triage, risk, and a violation probability.

## Model-only contract

```text
agent/tool request -> one selected System One model -> typed decision
```

- No deterministic override changes a model verdict.
- No generic LLM JSON adapter or ensemble is used.
- Provider errors return unavailable; they never turn into an allow/review/block fallback.
- Use redacted, minimal evidence only.

## Providers

| Provider | Runtime | Purpose |
| --- | --- | --- |
| `jev` | TypeSafe hosted API | Hosted reference baseline; requires `TYPESAFE_API_KEY` |
| `laya` | Official local Laya server | Purpose-built System One baseline |
| `tamev` | Local TAMEV Nano | Tiny CPU-oriented decision-model baseline |
| `ideanjev` | Local Qwen 3.5 4B + adapter | Larger Jev-style candidate, loaded in 4-bit CUDA mode |

Local checkpoints and cloned research source live under `work/`, which is intentionally ignored by Git.

## Results so far

All results use the included frozen synthetic DLP and triage corpora. They are research indicators, not claims about real-world DLP performance.

| Provider | Exact DLP accuracy | Unsafe-allow rate | Block recall | p50 latency |
| --- | ---: | ---: | ---: | ---: |
| Laya typed-decisions | 27.6% | 86.7% | 0.0% | 105 ms |
| TAMEV Nano | 37.9% | 93.3% | 6.7% | 513 ms |
| IdeaNJEV 4-bit | 48.3% | 0.0% | 53.3% | 2,264 ms |

Neither completed local baseline is suitable for DLP enforcement without a realistic labelled DLP dataset, held-out testing, and calibration.

## Prerequisites

- Python 3.10+
- For Laya: a Jev-compatible service on port `8001`
- For TAMEV: Nano files under `work/models/tamev-nano`
- For IdeaNJEV: an NVIDIA GPU, `peft`, `bitsandbytes`, Qwen 3.5 4B weights, and the adapter

The CUDA research environment used here is:

```text
C:\Users\mandi\Documents\Codex\2026-07-30\d\work\jlens-gpu-clean\Scripts\python.exe
```

## Run benchmarks

```powershell
python benchmark.py --provider jev
python benchmark.py --provider laya
python benchmark.py --provider tamev
python benchmark.py --provider ideanjev
```

Reports are written to `outputs/benchmark-<provider>.json`, also ignored by Git.

### Jev

```powershell
$env:TYPESAFE_API_KEY = "..."
python benchmark.py --provider jev
```

### Laya

Start Laya at `http://127.0.0.1:8001/v1/systemone`, then:

```powershell
$env:LAYA_BASE_URL = "http://127.0.0.1:8001/v1/systemone"
$env:LAYA_MODEL = "laya-typed-decisions"
python benchmark.py --provider laya
```

### TAMEV Nano

```powershell
$env:HF_HOME = "$PWD\work\huggingface-cache"
$env:HF_HUB_OFFLINE = "1"
$env:TAMEV_MODEL_DIR = "$PWD\work\models\tamev-nano"
python benchmark.py --provider tamev
```

### IdeaNJEV 4-bit

```powershell
$env:HF_HOME = "$PWD\work\huggingface-cache"
$env:HF_HUB_OFFLINE = "1"
$env:IDEANJEV_SOURCE_DIR = "$PWD\work\sources\ideanjev"
$env:IDEANJEV_BASE_DIR = "$PWD\work\models\qwen3.5-4b"
$env:IDEANJEV_ADAPTER_DIR = "$PWD\work\models\ideanjev-adapter"
python benchmark.py --provider ideanjev
```

The 4-bit path requires:

```powershell
python -m pip install peft bitsandbytes
```

## Demo and verification

```powershell
python server.py
python -m unittest -v
python -m py_compile dlp_gate.py server.py benchmark.py
```

Open `http://127.0.0.1:8000`. A UI evaluation makes one model inference; every displayed field derives from that same answer.

## Push-ready checklist

```powershell
git status
git add README.md .gitignore dlp_gate.py server.py benchmark.py frontend/src/main.jsx test_dlp_gate.py corpus.jsonl triage_corpus.jsonl
git commit -m "Add Jev-style local model research lanes"
git branch -M main
git remote add origin https://github.com/MandilKarki/systemone-dlp-gateway.git
git push -u origin main
```

If `origin` already exists, use:

```powershell
git remote set-url origin https://github.com/MandilKarki/systemone-dlp-gateway.git
```
