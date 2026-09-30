from __future__ import annotations
import argparse, json, statistics, time
from pathlib import Path
from dlp_gate import classify_and_triage, decide, ideanjev_provider, jev_provider, laya_provider, tamev_provider

def percentile(xs, p):
    return sorted(xs)[min(len(xs)-1, round((len(xs)-1)*p))]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("jev", "laya", "tamev", "ideanjev"), required=True)
    args = parser.parse_args()
    provider = {"jev":jev_provider, "laya":laya_provider, "tamev":tamev_provider, "ideanjev":ideanjev_provider}[args.provider]
    rows, latencies = [], []
    for line in Path("corpus.jsonl").read_text().splitlines():
        case = json.loads(line); start = time.perf_counter()
        result = decide(case["destination"], case["action"], case["evidence"], provider)
        latency = (time.perf_counter()-start)*1000; latencies.append(latency)
        rows.append({**case, "actual":result.verdict, "sensitivity":result.sensitivity,
                     "probability":result.probability, "reason":result.reason, "latency_ms":round(latency,2)})
    expected_blocks = [r for r in rows if r["expected"] == "block"]
    actual_blocks = [r for r in rows if r["actual"] == "block"]
    unsafe_allows = [r for r in rows if r["expected"] == "block" and r["actual"] == "allow"]
    summary = {"provider":args.provider, "cases":len(rows),
      "exact_accuracy":sum(r["expected"]==r["actual"] for r in rows)/len(rows),
      "unsafe_allow_rate":len(unsafe_allows)/len(expected_blocks),
      "block_recall":sum(r["actual"]=="block" for r in expected_blocks)/len(expected_blocks),
      "block_precision":sum(r["expected"]=="block" for r in actual_blocks)/len(actual_blocks) if actual_blocks else 0,
      "review_rate":sum(r["actual"]=="review" for r in rows)/len(rows),
      "latency_ms":{"p50":round(percentile(latencies,.5),2), "p95":round(percentile(latencies,.95),2)}}
    triage_rows = []
    for line in Path("triage_corpus.jsonl").read_text().splitlines():
        case = json.loads(line)
        expected_pii, expected_triage = case.pop("pii_type"), case.pop("triage")
        prediction = classify_and_triage(case["evidence"], provider)
        triage_rows.append({**case, "expected_pii_type":expected_pii,
                            "expected_triage":expected_triage, **prediction})
    summary["pii_exact_accuracy"] = sum(r["pii_type"] == r["expected_pii_type"] for r in triage_rows) / len(triage_rows)
    summary["triage_exact_accuracy"] = sum(r["triage"] == r["expected_triage"] for r in triage_rows) / len(triage_rows)
    output = {"summary":summary,"dlp_cases":rows,"triage_cases":triage_rows}; Path("outputs").mkdir(exist_ok=True)
    path = Path("outputs") / f"benchmark-{args.provider}.json"; path.write_text(json.dumps(output, indent=2))
    print(json.dumps(summary, indent=2)); print(f"Saved {path}")
if __name__ == "__main__": main()
