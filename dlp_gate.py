"""Model-only Jev/Laya DLP research gateway."""
from __future__ import annotations
import json, os, re, sys, threading, urllib.request
from dataclasses import dataclass

SENSITIVE = {
    "secret": ("<AWS_KEY>", "<TOKEN>", "<SECRET>", "<PRIVATE_KEY>", "api key", "password"),
    "pii": ("<EMAIL>", "<PHONE>", "<ADDRESS>", "<SSN>", "ssn"),
    "health": ("patient", "diagnosis", "treatment"),
    "financial": ("revenue forecast", "earnings model", "confidential"),
    "source_code": ("source code", "proprietary source"),
}

# These recognizers intentionally cover only high-confidence formats. They are
# a deterministic safety net, not a replacement for organization-specific DLP
# recognizers or a trained PII model.
SECRET_PATTERNS = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),  # AWS access-key IDs
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),  # GitHub tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),  # JWT
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "phone": re.compile(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]\d{4}(?!\w)"),
    "ssn": re.compile(r"\b(?!000|666|9\d\d)\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b"),
}

@dataclass
class Decision:
    verdict: str
    sensitivity: str
    probability: float
    reason: str

def pii_type(evidence: str) -> str:
    """Return the highest-risk recognized PII type, if any."""
    lowered = evidence.lower()
    for kind, marker in (("ssn", "<ssn>"), ("email", "<email>"), ("phone", "<phone>"), ("address", "<address>")):
        if marker in lowered:
            return kind
    for kind in ("ssn", "email", "phone"):
        if PII_PATTERNS[kind].search(evidence):
            return kind
    return "none"


def detect(evidence: str) -> str:
    value = evidence.lower()
    if any(pattern.search(evidence) for pattern in SECRET_PATTERNS):
        return "secret"
    if pii_type(evidence) != "none":
        return "pii"
    for label, tokens in SENSITIVE.items():
        if any(token.lower() in value for token in tokens): return label
    return "public"

def decision_questions() -> dict:
    """The shared typed schema used for the Jev and Laya research lanes."""
    return {
      "sensitivity": {"type":"choice", "instructions":"Classify the redacted evidence.", "criteria": {
        "public":"non-sensitive public information", "pii":"personal data", "secret":"credential or secret",
        "health":"health information", "financial":"non-public financial information", "source_code":"proprietary code"}},
      "pii_type": {"type":"choice", "instructions":"Select the highest-risk PII type present, or none.", "criteria": {
        "none":"no PII", "email":"email address", "phone":"phone number", "address":"street/home address", "ssn":"government identifier"}},
      "triage": {"type":"choice", "instructions":"Choose the owning workflow. Use allow only for non-sensitive material.", "criteria": {
        "allow":"no review needed", "privacy_review":"privacy or health-data review", "security_incident":"credential/security response", "business_review":"confidential business-data review"}},
      "verdict": {"type":"choice", "instructions":"Decide the DLP outcome for this exact destination and action.", "criteria": {
        "allow":"transfer is permitted", "review":"a human must review before transfer", "block":"transfer must not proceed"}},
      "risk": {"type":"score", "instructions":"Rate egress exposure risk.", "criteria":["none","low","moderate","high"]},
      "violates": {"type":"noul", "instructions":"Would sending this to the stated destination violate DLP policy?"}}


def system_one_provider(state: dict, *, endpoint: str, model: str, token: str | None = None) -> dict:
    """Call a Jev-compatible System One endpoint and return its typed answers."""
    payload = json.dumps({"model": model, "state": state, "questions": decision_questions()}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(endpoint, data=payload,
      headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())["answers"]

def jev_provider(state: dict) -> dict:
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is required for --provider jev")
    return system_one_provider(state, endpoint="https://api.typesafe.ai/v1/systemone", model="jev-latest", token=key)


def laya_provider(state: dict) -> dict:
    """Local, Jev-compatible Laya decision service; no evidence leaves the host."""
    endpoint = os.environ.get("LAYA_BASE_URL", "http://127.0.0.1:8001/v1/systemone")
    model = os.environ.get("LAYA_MODEL", "laya-typed-decisions")
    return system_one_provider(state, endpoint=endpoint, model=model, token=os.environ.get("LAYA_API_KEY"))


_model_lock = threading.Lock()
_tamev_model = None
_tamev_tokenizer = None
_ideanjev_model = None


def tamev_provider(state: dict) -> dict:
    """Use the local TAMEV-Nano model for each typed decision question."""
    global _tamev_model, _tamev_tokenizer
    with _model_lock:
        if _tamev_model is None:
            from transformers import AutoModel, AutoTokenizer
            model_dir = os.environ.get("TAMEV_MODEL_DIR", "work/models/tamev-nano")
            _tamev_tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True)
            _tamev_model = AutoModel.from_pretrained(model_dir, trust_remote_code=True, local_files_only=True).eval()
    state_text = json.dumps(state, sort_keys=True)

    def choose(instructions: str, criteria: dict[str, str]) -> tuple[str, float]:
        labels = list(criteria)
        result = _tamev_model.predict_decision(
            state=state_text, question=instructions,
            options=[f"{label}: {criteria[label]}" for label in labels], tokenizer=_tamev_tokenizer,
        )
        return labels[result["best_index"]], float(result["confidence"])

    answers = {}
    for name, question in decision_questions().items():
        if question["type"] == "choice":
            choice, confidence = choose(question["instructions"], question["criteria"])
            answers[name] = {"choice": choice, "confidence": confidence}
        elif question["type"] == "noul":
            choice, confidence = choose(question["instructions"], {"false": "No, the statement is false.", "true": "Yes, the statement is true."})
            answers[name] = {"noul": choice == "true", "confidence": confidence}
        elif question["type"] == "score":
            choice, confidence = choose(question["instructions"], {str(i): label for i, label in enumerate(question["criteria"])})
            answers[name] = {"score": int(choice), "confidence": confidence}
    return answers


def ideanjev_provider(state: dict) -> dict:
    """Use local 4-bit IdeaNJEV and preserve its model probabilities."""
    global _ideanjev_model
    with _model_lock:
        if _ideanjev_model is None:
            source_dir = os.environ.get("IDEANJEV_SOURCE_DIR", "work/sources/ideanjev")
            if source_dir not in sys.path:
                sys.path.insert(0, source_dir)
            from ideanjev.model import IdeaNJEV
            _ideanjev_model = IdeaNJEV(
                base_model=os.environ.get("IDEANJEV_BASE_DIR", "work/models/qwen3.5-4b"),
                adapter=os.environ.get("IDEANJEV_ADAPTER_DIR", "work/models/ideanjev-adapter"),
                device="cuda", load_in_4bit=True,
            )
    raw = _ideanjev_model.decide(state, decision_questions())["answers"]
    answers = {}
    for name, question in decision_questions().items():
        item = raw[name]
        if question["type"] == "choice":
            answers[name] = {"choice": item["answer"], "confidence": item["confidence"]}
        elif question["type"] == "noul":
            answers[name] = {"noul": float(item["probabilities"].get("true", 0.0)), "confidence": item["confidence"]}
        elif question["type"] == "score":
            answers[name] = {"score": int(item["answer"]), "confidence": item["confidence"]}
    return answers

def decide(destination: str, action: str, evidence: str, provider) -> Decision:
    """Return the selected model's verdict without policy overrides or fallback."""
    state = {"destination_trust":destination, "action":action, "evidence":evidence}
    answer = provider(state)
    sensitivity = answer["sensitivity"]["choice"]
    probability = float(answer["violates"]["noul"])
    verdict = answer["verdict"]["choice"]
    if verdict not in {"allow", "review", "block"}:
        raise ValueError("model returned an invalid DLP verdict")
    return Decision(verdict, sensitivity, probability, "model decision")

def classify_and_triage(evidence: str, provider) -> dict:
    """Return the selected model's PII and ownership labels without a fallback."""
    answer = provider({"destination_trust":"unknown", "action":"intake", "evidence":evidence})
    return {"pii_type":answer["pii_type"]["choice"], "triage":answer["triage"]["choice"],
            "confidence":min(float(answer["pii_type"].get("confidence", 0.0)), float(answer["triage"].get("confidence", 0.0)))}


def evaluate(destination: str, action: str, evidence: str, provider) -> tuple[Decision, dict]:
    """Run one selected-model inference and derive all displayed fields from it."""
    state = {"destination_trust": destination, "action": action, "evidence": evidence}
    answer = provider(state)
    verdict = answer["verdict"]["choice"]
    if verdict not in {"allow", "review", "block"}:
        raise ValueError("model returned an invalid DLP verdict")
    decision = Decision(verdict, answer["sensitivity"]["choice"], float(answer["violates"]["noul"]), "model decision")
    triage = {"pii_type": answer["pii_type"]["choice"], "triage": answer["triage"]["choice"],
              "confidence": min(float(answer["pii_type"].get("confidence", 0.0)), float(answer["triage"].get("confidence", 0.0)))}
    return decision, triage
