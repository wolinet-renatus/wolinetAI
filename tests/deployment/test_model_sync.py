import unittest
from unittest.mock import patch
import scripts.deploy.sync_xinference_models as s


class ModelSyncEndpointTests(unittest.TestCase):
    def test_inference_urls_includes_local_and_fallback_aliases(self) -> None:
        urls = s._inference_urls()
        self.assertIn("http://mitambo:9997", urls)
        self.assertIn("http://wolinet-mitambo:9997", urls)
        self.assertIn("http://wolinet_mitambo:9997", urls)
        self.assertIn("http://tasks.mitambo:9997", urls)
        self.assertIn("http://172.17.0.1:9997", urls)
        self.assertIn("http://host.docker.internal:9997", urls)
        self.assertIn("https://mitambo.wolinet.com", urls)

    def test_inference_urls_respects_compose_project_name(self) -> None:
        with patch.dict("os.environ", {"COMPOSE_PROJECT_NAME": "wolinetai"}):
            urls = s._inference_urls()
            self.assertIn("http://wolinetai-mitambo:9997", urls)
            self.assertIn("http://wolinetai_mitambo:9997", urls)
            self.assertIn("http://tasks.wolinetai_mitambo:9997", urls)

    def test_fetch_active_models_from_urls_raises_typed_error(self) -> None:
        with patch.object(s, "_inference_urls", return_value=["http://127.0.0.1:1"]):
            with self.assertRaises(s.XinferenceUnavailableError):
                s._fetch_active_models_from_urls("test-key")

    def test_upsert_model_payload_includes_key_and_reasoning_spec(self) -> None:
        captured = {}
        def fake_request(url: str, key: str, method: str, payload: dict) -> dict:
            captured["url"] = url
            captured["payload"] = payload
            return {"status": "ok"}

        with patch.object(s, "_request_json", side_effect=fake_request):
            s._upsert_model("http://lango:4000", "test-master", "tiny-llama", "tiny-llama",
                            "http://mitambo:9997/v1", "test-inf-key", None)

        self.assertIn("payload", captured)
        model_info = captured["payload"].get("model_info", {})
        self.assertEqual(model_info.get("key"), "tiny-llama")
        self.assertIs(model_info.get("supports_reasoning"), False)
        self.assertEqual(captured["payload"]["litellm_params"]["model"], "openai/tiny-llama")


if __name__ == "__main__":
    unittest.main()
