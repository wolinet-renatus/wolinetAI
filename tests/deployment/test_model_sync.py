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


if __name__ == "__main__":
    unittest.main()
