import unittest

from dlp_gate import decide, evaluate


def model_answer(verdict="review"):
    return {
        "sensitivity": {"choice": "pii", "confidence": 0.71},
        "pii_type": {"choice": "email", "confidence": 0.71},
        "triage": {"choice": "privacy_review", "confidence": 0.71},
        "violates": {"noul": 0.83},
        "verdict": {"choice": verdict},
    }


class ModelOnlyGatewayTests(unittest.TestCase):
    def test_model_verdict_is_returned_without_a_policy_override(self):
        result = decide("public", "paste", "An AWS key AKIAIOSFODNN7EXAMPLE", lambda _: model_answer("allow"))
        self.assertEqual("allow", result.verdict)
        self.assertEqual("model decision", result.reason)

    def test_one_inference_produces_decision_and_triage(self):
        calls = []
        def provider(state):
            calls.append(state)
            return model_answer("block")
        decision, triage = evaluate("public", "paste", "jane@example.com", provider)
        self.assertEqual(1, len(calls))
        self.assertEqual("block", decision.verdict)
        self.assertEqual("email", triage["pii_type"])

    def test_provider_errors_are_not_converted_to_a_fallback_verdict(self):
        with self.assertRaises(RuntimeError):
            decide("public", "paste", "text", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))


if __name__ == "__main__":
    unittest.main()
